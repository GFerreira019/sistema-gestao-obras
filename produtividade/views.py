from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.contrib import messages
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta
import calendar
from .forms import ApontamentoForm
from .models import Apontamento, Projeto, Colaborador, Setor, Veiculo, CodigoCliente, CentroCusto
from django.contrib.auth.models import Group

# ==============================================================================
# LÓGICA DE CONTROLE DE ACESSO (RBAC)
# Helpers para validação de permissões e hierarquia de usuários
# ==============================================================================

def is_user_in_group(user, group_name):
    """Verifica se o usuário pertence a um grupo específico."""
    return user.groups.filter(name=group_name).exists()

def is_owner(user):
    """Verifica se o usuário possui permissão de Superusuário (Owner)."""
    return user.is_superuser

def is_admin_or_gestor(user):
    """Verifica se o usuário possui perfil Administrativo ou Gestor."""
    return is_user_in_group(user, 'GESTOR') or is_user_in_group(user, 'ADMINISTRATIVO')

def is_operacional(user):
    """Identifica se o usuário é do nível Operacional (Restrito)."""
    return user.is_authenticated and not is_owner(user) and not is_admin_or_gestor(user)

@login_required
def home_redirect_view(request):
    """Redireciona a raiz do sistema para o menu principal."""
    return redirect('home_menu')

# ==============================================================================
# VIEWS DE OPERAÇÃO (CRIAR, EDITAR, EXCLUIR)
# Gerenciam o fluxo de persistência de dados do Timesheet
# ==============================================================================

@login_required
def apontamento_atividade_view(request):
    """View para registro de novos apontamentos diários."""
    user_kwargs = {'user': request.user}
    
    if request.method == 'POST':
        form = ApontamentoForm(request.POST, **user_kwargs)
        if form.is_valid():
            apontamento = form.save(commit=False)
            apontamento.registrado_por = request.user
            
            # --- Tratamento de Auxiliares ---
            if form.cleaned_data.get('registrar_auxiliar'):
                apontamento.auxiliar = form.cleaned_data.get('auxiliar_selecao')
                apontamento.auxiliares_extras_ids = form.cleaned_data.get('auxiliares_extras_list')
            else:
                apontamento.auxiliar = None
                apontamento.auxiliares_extras_ids = None

            # --- Tratamento de Veículo (Lógica Híbrida) ---
            if form.cleaned_data.get('registrar_veiculo'):
                selection = form.cleaned_data.get('veiculo_selecao')
                if selection == 'OUTRO':
                    apontamento.veiculo = None
                    apontamento.veiculo_manual_modelo = form.cleaned_data.get('veiculo_manual_modelo')
                    apontamento.veiculo_manual_placa = form.cleaned_data.get('veiculo_manual_placa')
                else:
                    try:
                        apontamento.veiculo = Veiculo.objects.get(pk=selection)
                        apontamento.veiculo_manual_modelo = None
                        apontamento.veiculo_manual_placa = None
                    except Veiculo.DoesNotExist:
                        apontamento.veiculo = None
            else:
                apontamento.veiculo = None
                apontamento.veiculo_manual_modelo = None
                apontamento.veiculo_manual_placa = None

            apontamento.save()
            messages.success(request, f"Registro de {apontamento.colaborador} salvo com sucesso!")
            return redirect('novo_apontamento')
    else:
        # Preenchimento automático de data e hora para facilitar UX
        now_local = timezone.localtime(timezone.now())
        initial_data = {
            'data_apontamento': now_local.strftime('%Y-%m-%d'),
            'hora_inicio': now_local.strftime('%H:%M'),
        }
        form = ApontamentoForm(initial=initial_data, **user_kwargs)

    context = {
        'form': form,
        'titulo': 'Timesheet',
        'subtitulo': 'Preencha os dados de horário e local de trabalho.',
        'is_editing': False
    }
    return render(request, 'produtividade/apontamento_form.html', context)


@login_required
@user_passes_test(is_owner)
def editar_apontamento_view(request, pk):
    """View para edição de registros existentes (Restrito a Owners)."""
    apontamento = get_object_or_404(Apontamento, pk=pk)
    user_kwargs = {'user': request.user, 'instance': apontamento}

    if request.method == 'POST':
        form = ApontamentoForm(request.POST, **user_kwargs)
        if form.is_valid():
            obj = form.save(commit=False)
            # Limpeza manual de auxiliares caso o checkbox seja desmarcado
            if not form.cleaned_data.get('registrar_auxiliar'):
                obj.auxiliar = None
                obj.auxiliares_extras_ids = None
            obj.save()
            messages.success(request, "Apontamento atualizado com sucesso!")
            return redirect('historico_apontamentos')
    else:
        # Recupera estados de checkbox para exibição correta no form de edição
        initial_data = {}
        if apontamento.veiculo or apontamento.veiculo_manual_placa:
            initial_data['registrar_veiculo'] = True
        if apontamento.auxiliar:
            initial_data['registrar_auxiliar'] = True
            initial_data['auxiliares_extras_list'] = apontamento.auxiliares_extras_ids
        
        form = ApontamentoForm(initial=initial_data, **user_kwargs)

    context = {
        'form': form,
        'titulo': 'Editar Apontamento',
        'subtitulo': f'Editando registro #{apontamento.id} de {apontamento.colaborador}',
        'is_editing': True,
        'apontamento_id': pk
    }
    return render(request, 'produtividade/apontamento_form.html', context)


@login_required
@user_passes_test(is_owner)
def excluir_apontamento_view(request, pk):
    """View para exclusão definitiva de registros (Restrito a Owners)."""
    apontamento = get_object_or_404(Apontamento, pk=pk)
    apontamento.delete()
    messages.success(request, "Apontamento excluído com sucesso.")
    return redirect('historico_apontamentos')


@login_required
def configuracoes_view(request):
    """Exibe configurações de conta e opções de alteração de senha."""
    context = {
        'titulo': 'Configurações do Usuário',
        'change_password_url': '/accounts/password_change/',
    }
    return render(request, 'produtividade/configuracoes.html', context)

# ==============================================================================
# VIEW DE HISTÓRICO E RELATÓRIOS
# Gerencia filtros de data, permissões de visão e explosão de auxiliares
# ==============================================================================

@login_required
def historico_apontamentos_view(request):
    """View de visualização do histórico com filtragem inteligente por data e perfil."""
    user = request.user
    queryset = Apontamento.objects.all()

    # --- 1. Gestão de Filtros de Período ---
    period = request.GET.get('period')
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=6) # Padrão última semana
    current_period = '7'

    if period:
        try:
            days = int(period)
            start_date = end_date - timedelta(days=days - 1)
            current_period = period
        except ValueError: pass
    elif start_date_str and end_date_str:
        try:
            start_date = timezone.datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = timezone.datetime.strptime(end_date_str, '%Y-%m-%d').date()
            current_period = 'custom'
        except ValueError: pass

    # --- 2. Aplicação de Limites de Segurança (30 dias para não-owners) ---
    if not is_owner(user):
        limit_date = timezone.now().date() - timedelta(days=30)
        if start_date < limit_date:
            start_date = limit_date
        queryset = queryset.filter(data_apontamento__gte=limit_date)

    queryset = queryset.filter(data_apontamento__gte=start_date, data_apontamento__lte=end_date)

    # --- 3. Filtragem Baseada em Perfil (RBAC) ---
    try:
        colaborador_logado = Colaborador.objects.get(user_account=user)
    except Colaborador.DoesNotExist:
        colaborador_logado = None

    if is_owner(user): pass 
    elif is_admin_or_gestor(user) and colaborador_logado:
        setores_gerenciados = colaborador_logado.setores_gerenciados.all()
        if setores_gerenciados.exists():
            queryset = queryset.filter(
                Q(colaborador__setor__in=setores_gerenciados) | Q(registrado_por=user)
            )
        else:
            queryset = queryset.filter(registrado_por=user)
    else:
        queryset = queryset.filter(registrado_por=user)

    # --- 4. Processamento da Lista e Explosão de Auxiliares ---
    apontamentos_db = queryset.order_by('-data_apontamento', '-id')
    historico_lista = []

    for item in apontamentos_db:
        # Lógica de referência de local
        if item.local_execucao == 'INT':
            if item.projeto:
                p_cod = item.projeto.codigo if item.projeto.codigo else ""
                local_ref = f"{p_cod} - {item.projeto.nome}" if p_cod else f"{item.projeto.nome}"
            elif item.codigo_cliente:
                local_ref = f"{item.codigo_cliente.codigo} - {item.codigo_cliente.nome}"
            else:
                local_ref = "Obra/Cliente não informado"
        else:
            local_ref = item.centro_custo.nome if item.centro_custo else "Externo"
            if item.projeto: local_ref += f" (Obra: {item.projeto.codigo})"
            elif item.codigo_cliente: local_ref += f" (Cli: {item.codigo_cliente.codigo})"

        # Formatação de exibição do Veículo
        if item.veiculo: veiculo_display = str(item.veiculo)
        elif item.veiculo_manual_placa: veiculo_display = f"{item.veiculo_manual_modelo} - {item.veiculo_manual_placa} (Externo)"
        else: veiculo_display = ""

        # Formatação de exibição do Usuário
        reg_user = item.registrado_por
        user_display = f"{reg_user.first_name} {reg_user.last_name}" if reg_user and reg_user.first_name else (reg_user.username if reg_user else "Sistema")

        base_dict = {
            'id': item.id, 'data': item.data_apontamento, 'local_ref': local_ref,
            'inicio': item.hora_inicio, 'termino': item.hora_termino,
            'local_tipo': item.get_local_execucao_display(), 'obs': item.ocorrencias,
            'tangerino': item.local_inicio_jornada, 'tangerino_obs': item.local_inicio_jornada_outros,
            'registrado_em': item.data_registro, 'registrado_por_str': user_display
        }

        # Adiciona colaborador principal
        row_main = base_dict.copy()
        row_main.update({'nome': item.colaborador.nome_completo, 'cargo': item.colaborador.cargo, 'veiculo': veiculo_display, 'is_auxiliar': False})
        historico_lista.append(row_main)

        # "Explode" auxiliares como linhas separadas no histórico
        auxiliares_a_exibir = []
        if item.auxiliar: auxiliares_a_exibir.append(item.auxiliar)
        if item.auxiliares_extras_ids:
            try:
                ids = [int(x) for x in item.auxiliares_extras_ids.split(',') if x.strip()]
                auxiliares_a_exibir.extend(Colaborador.objects.filter(id__in=ids))
            except ValueError: pass

        for aux in auxiliares_a_exibir:
            row_aux = base_dict.copy()
            row_aux.update({'nome': aux.nome_completo, 'cargo': aux.cargo, 'veiculo': "", 'is_auxiliar': True})
            historico_lista.append(row_aux)

    context = {
        'titulo': "Histórico",
        'apontamentos_lista': historico_lista,
        'show_user_column': not is_operacional(user),
        'is_owner': is_owner(user),
        'current_period': current_period,
        'start_date_val': start_date.strftime('%Y-%m-%d'),
        'end_date_val': end_date.strftime('%Y-%m-%d'),
    }
    return render(request, 'produtividade/historico_apontamentos.html', context)

# ==============================================================================
# APIS AJAX & UTILITÁRIOS
# Endpoints para dinamismo do frontend (Selects, Calendário, Info)
# ==============================================================================

@login_required
def apontamento_sucesso_view(request):
    """Página de feedback positivo após registro."""
    return render(request, 'produtividade/apontamento_sucesso.html')

@login_required
def get_projeto_info_ajax(request, projeto_id):
    """Retorna o nome de um projeto via AJAX."""
    projeto = get_object_or_404(Projeto, pk=projeto_id)
    return JsonResponse({'nome_projeto': projeto.nome})

@login_required
def get_colaborador_info_ajax(request, colaborador_id):
    """Retorna o cargo de um colaborador via AJAX."""
    colaborador = get_object_or_404(Colaborador, pk=colaborador_id)
    return JsonResponse({'cargo': colaborador.cargo})

@login_required
def get_auxiliares_ajax(request):
    """Lista colaboradores elegíveis como auxiliares para Select2."""
    auxs = Colaborador.objects.filter(cargo__in=['AUXILIAR TECNICO', 'OFICIAL DE SISTEMAS']).values('id', 'nome_completo')
    return JsonResponse({'auxiliares': list(auxs)})

@login_required
def home_view(request):
    """Menu principal (Dashboard inicial)."""
    return render(request, 'produtividade/home.html')

@login_required
def get_centro_custo_info_ajax(request, cc_id):
    """Retorna regras de alocação do Centro de Custo via AJAX."""
    cc = get_object_or_404(CentroCusto, pk=cc_id)
    return JsonResponse({'permite_alocacao': cc.permite_alocacao})

@login_required
def get_calendar_status_ajax(request):
    """Retorna status de preenchimento diário para renderização do calendário UX."""
    try:
        month = int(request.GET.get('month'))
        year = int(request.GET.get('year'))
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Parâmetros inválidos'}, status=400)
    
    user = request.user
    if is_owner(user): return JsonResponse({'is_owner': True, 'days': []})

    try:
        colaborador = Colaborador.objects.get(user_account=user)
    except Colaborador.DoesNotExist:
        return JsonResponse({'error': 'Colaborador não encontrado'}, status=400)

    _, num_days = calendar.monthrange(year, month)
    start_date = timezone.datetime(year, month, 1).date()
    end_date = timezone.datetime(year, month, num_days).date()

    dias_com_apontamento = Apontamento.objects.filter(
        colaborador=colaborador, data_apontamento__gte=start_date, data_apontamento__lte=end_date
    ).values_list('data_apontamento', flat=True).distinct()
    
    dias_set = set(d.strftime('%Y-%m-%d') for d in dias_com_apontamento)
    days_data = []
    today = timezone.now().date()

    for day in range(1, num_days + 1):
        current_date = timezone.datetime(year, month, day).date()
        date_str = current_date.strftime('%Y-%m-%d')
        status = 'filled' if date_str in dias_set else ('future' if current_date > today else 'missing')
        days_data.append({'date': date_str, 'day': day, 'status': status})

    return JsonResponse({'is_owner': False, 'days': days_data})