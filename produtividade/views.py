from django.shortcuts import render, redirect, get_object_or_404, HttpResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.contrib import messages
from django.db.models import Q, Count
from django.utils import timezone
from datetime import timedelta, datetime, date
import calendar
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
import json
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt

# Imports locais
from .forms import ApontamentoForm
from .models import Apontamento, Projeto, Colaborador, Setor, Veiculo, CodigoCliente, CentroCusto

# ==============================================================================
# 1. LÓGICA DE CONTROLE DE ACESSO (RBAC)
# ==============================================================================

def is_user_in_group(user, group_name):
    """Verifica se o usuário pertence a um grupo específico."""
    return user.groups.filter(name=group_name).exists()

def is_owner(user):
    """Verifica se é superusuário (Auditores/TI)."""
    return user.is_superuser

def is_admin_or_gestor(user):
    """Verifica permissões de gestão."""
    return is_user_in_group(user, 'GESTOR') or is_user_in_group(user, 'ADMINISTRATIVO')

def is_operacional(user):
    """Verifica se é usuário padrão (Colaborador)."""
    return user.is_authenticated and not is_owner(user) and not is_admin_or_gestor(user)

@login_required
def home_redirect_view(request):
    """Redireciona para a home correta."""
    return redirect('home_menu')

@login_required
def home_view(request):
    """Renderiza o menu principal."""
    return render(request, 'produtividade/home.html')

@login_required
def configuracoes_view(request):
    """Tela de configurações do usuário."""
    context = {
        'titulo': 'Configurações do Usuário',
        'change_password_url': '/accounts/password_change/',
    }
    return render(request, 'produtividade/configuracoes.html', context)

# ==============================================================================
# 2. VIEWS DE OPERAÇÃO (CRIAR E LISTAR)
# ==============================================================================

@login_required
def apontamento_atividade_view(request):
    """
    View principal para CRIAÇÃO de novos apontamentos.
    Gerencia:
    - Salvamento do Form principal.
    - Lógica de Veículo (Banco ou Manual).
    - Lógica de Auxiliares (Principal + Extras).
    """
    user_kwargs = {'user': request.user}
    
    if request.method == 'POST':
        form = ApontamentoForm(request.POST, **user_kwargs)
        if form.is_valid():
            apontamento = form.save(commit=False)
            apontamento.registrado_por = request.user
            
            # 1. Lógica de Auxiliar Principal
            if form.cleaned_data.get('registrar_auxiliar'):
                apontamento.auxiliar = form.cleaned_data.get('auxiliar_selecao')
            else:
                apontamento.auxiliar = None

            # 2. Lógica de Veículo (Híbrida)
            if form.cleaned_data.get('registrar_veiculo'):
                selection = form.cleaned_data.get('veiculo_selecao')
                if selection == 'OUTRO':
                    # Veículo Manual
                    apontamento.veiculo = None
                    apontamento.veiculo_manual_modelo = form.cleaned_data.get('veiculo_manual_modelo')
                    apontamento.veiculo_manual_placa = form.cleaned_data.get('veiculo_manual_placa')
                else:
                    # Veículo do Banco
                    try:
                        apontamento.veiculo = Veiculo.objects.get(pk=selection)
                        apontamento.veiculo_manual_modelo = None
                        apontamento.veiculo_manual_placa = None
                    except Veiculo.DoesNotExist:
                        apontamento.veiculo = None
            else:
                # Sem veículo
                apontamento.veiculo = None
                apontamento.veiculo_manual_modelo = None
                apontamento.veiculo_manual_placa = None

            apontamento.save() 

            # 3. Salva os Extras no Many-To-Many (Necessário após o save do objeto)
            if form.cleaned_data.get('registrar_auxiliar'):
                ids_string = form.cleaned_data.get('auxiliares_extras_list')
                if ids_string:
                    ids_list = [int(x) for x in ids_string.split(',') if x.strip().isdigit()]
                    apontamento.auxiliares_extras.set(ids_list)
                else:
                    apontamento.auxiliares_extras.clear()
            else:
                apontamento.auxiliares_extras.clear()

            messages.success(request, f"Registro de {apontamento.colaborador} salvo com sucesso!")
            return redirect('novo_apontamento')
    else:
        now_local = timezone.localtime(timezone.now())
        initial_data = {
            'data_apontamento': now_local.strftime('%d/%m/%Y'),
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
def historico_apontamentos_view(request):
    """
    View de Listagem com filtros de data e permissões de visualização.
    """
    user = request.user
    
    # Eager Loading para evitar N+1 queries
    queryset = Apontamento.objects.select_related(
        'projeto', 'codigo_cliente', 'colaborador', 
        'veiculo', 'centro_custo', 'registrado_por'
    ).prefetch_related('auxiliares_extras').all()

    # --- Filtros de Data ---
    period = request.GET.get('period')
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=6)
    current_period = '7'

    if period:
        try:
            days = int(period)
            start_date = end_date - timedelta(days=days - 1)
            current_period = period
            start_date_str = None
            end_date_str = None
        except ValueError:
            pass
    elif start_date_str and end_date_str:
        try:
            start_date = timezone.datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = timezone.datetime.strptime(end_date_str, '%Y-%m-%d').date()
            current_period = 'custom'
        except ValueError:
            pass

    queryset = queryset.filter(data_apontamento__gte=start_date, data_apontamento__lte=end_date)

    # --- Regras de Visualização (Quem vê o quê) ---
    if is_owner(user):
        pass # Owner vê tudo
    else:
        try:
            meu_perfil_colaborador = Colaborador.objects.get(user_account=user)
            # Vê registros feitos POR MIM ou ONDE EU SOU o colaborador
            queryset = queryset.filter(
                Q(registrado_por=user) | Q(colaborador=meu_perfil_colaborador)
            )
        except Colaborador.DoesNotExist:
            queryset = queryset.filter(registrado_por=user)
        
        # Limita histórico para não-admins (segurança/performance)
        limit_date = timezone.now().date() - timedelta(days=30)
        if start_date < limit_date:
            start_date = limit_date
        queryset = queryset.filter(data_apontamento__gte=limit_date)

    # Processamento para exibição
    apontamentos_db = queryset.order_by('-data_apontamento', '-id')
    historico_lista = []

    for item in apontamentos_db:
        # Formatação inteligente do Local
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
            if item.projeto:
                local_ref += f" (Obra: {item.projeto.codigo})"
            elif item.codigo_cliente:
                local_ref += f" (CLIENTE: {item.codigo_cliente.codigo})"

        # Formatação inteligente do Veículo
        if item.veiculo: 
            veiculo_display = str(item.veiculo)
        elif item.veiculo_manual_placa: 
            veiculo_display = f"{item.veiculo_manual_modelo} - {item.veiculo_manual_placa} (Externo)"
        else: 
            veiculo_display = ""

        reg_user = item.registrado_por
        user_display = f"{reg_user.first_name} {reg_user.last_name}" if reg_user and reg_user.first_name else (reg_user.username if reg_user else "Sistema")

        base_dict = {
            'id': item.id,
            'data': item.data_apontamento,
            'local_ref': local_ref,
            'inicio': item.hora_inicio,
            'termino': item.hora_termino,
            'local_tipo': item.get_local_execucao_display(),
            'obs': item.ocorrencias,
            'tangerino': item.local_inicio_jornada,
            'tangerino_obs': item.local_inicio_jornada_outros,
            'registrado_em': item.data_registro,
            'registrado_por_str': user_display,
            'em_plantao': item.em_plantao,
            'dorme_fora': item.dorme_fora,
            'motivo_ajuste': item.motivo_ajuste,
            'status_ajuste': item.status_ajuste, 
        }

        # Adiciona linha principal (Colaborador)
        row_main = base_dict.copy()
        row_main.update({'nome': item.colaborador.nome_completo, 'cargo': item.colaborador.cargo, 'veiculo': veiculo_display, 'is_auxiliar': False})
        historico_lista.append(row_main)

        # Adiciona linhas de Auxiliares (se houver) para visualização expandida
        auxiliares_a_exibir = []
        if item.auxiliar: auxiliares_a_exibir.append(item.auxiliar)
        
        extras = item.auxiliares_extras.all()
        auxiliares_a_exibir.extend(extras)

        for aux in auxiliares_a_exibir:
            row_aux = base_dict.copy()
            row_aux.update({'nome': aux.nome_completo, 'cargo': aux.cargo, 'veiculo': "", 'is_auxiliar': True})
            historico_lista.append(row_aux)

    context = {
        'titulo': "Histórico",
        'apontamentos_lista': historico_lista,
        'show_user_column': is_owner(user), 
        'is_owner': is_owner(user),
        'current_period': current_period,
        'start_date_val': start_date.strftime('%Y-%m-%d'),
        'end_date_val': end_date.strftime('%Y-%m-%d'),
    }
    return render(request, 'produtividade/historico_apontamentos.html', context)


# ==============================================================================
# 3. GESTÃO DE AJUSTES E EDIÇÃO (ADMINISTRATIVO)
# ==============================================================================

@login_required
def solicitar_ajuste_view(request, pk):
    """
    Permite que o usuário ou colaborador solicite um ajuste em um registro fechado.
    """
    apontamento = get_object_or_404(Apontamento, pk=pk)
    
    # Segurança: Só permite se o usuário for o dono do registro ou o colaborador vinculado
    is_autor = apontamento.registrado_por == request.user
    is_colaborador = False
    try:
        colab = Colaborador.objects.get(user_account=request.user)
        if apontamento.colaborador == colab:
            is_colaborador = True
    except Colaborador.DoesNotExist:
        pass

    if not (is_autor or is_colaborador or request.user.is_superuser):
         messages.error(request, "Você não tem permissão para solicitar ajuste neste registro.")
         return redirect('historico_apontamentos')

    if request.method == 'POST':
        motivo = request.POST.get('motivo_texto')
        if motivo:
            apontamento.motivo_ajuste = motivo
            apontamento.status_ajuste = 'PENDENTE'
            apontamento.save()
            messages.success(request, "Solicitação de ajuste enviada para a administração.")
        else:
            messages.warning(request, "É necessário descrever o motivo do ajuste.")
            
    return redirect('historico_apontamentos')


@login_required
@user_passes_test(is_owner)
def editar_apontamento_view(request, pk):
    """
    Edição completa do apontamento (Acesso Admin).
    Se o apontamento tinha uma solicitação de ajuste pendente, ela é automaticamente aprovada ao salvar.
    """
    apontamento = get_object_or_404(Apontamento, pk=pk)
    user_kwargs = {'user': request.user, 'instance': apontamento}

    if request.method == 'POST':
        form = ApontamentoForm(request.POST, **user_kwargs)
        if form.is_valid():
            obj = form.save(commit=False)
            
            # 1. Limpeza de Auxiliares
            if not form.cleaned_data.get('registrar_auxiliar'):
                obj.auxiliar = None

            # 2. Tratamento de Veículo
            if form.cleaned_data.get('registrar_veiculo'):
                selection = form.cleaned_data.get('veiculo_selecao')
                if selection == 'OUTRO':
                    obj.veiculo = None
                    obj.veiculo_manual_modelo = form.cleaned_data.get('veiculo_manual_modelo')
                    obj.veiculo_manual_placa = form.cleaned_data.get('veiculo_manual_placa')
                else:
                    try:
                        obj.veiculo = Veiculo.objects.get(pk=selection)
                        obj.veiculo_manual_modelo = None
                        obj.veiculo_manual_placa = None
                    except Veiculo.DoesNotExist:
                        obj.veiculo = None
            else:
                obj.veiculo = None
                obj.veiculo_manual_modelo = None
                obj.veiculo_manual_placa = None

            # 3. Aprovação Automática de Ajuste (se houver pendência)
            if obj.status_ajuste == 'PENDENTE':
                obj.status_ajuste = 'APROVADO'
            
            obj.save()

            # 4. Atualização do M2M Auxiliares
            if form.cleaned_data.get('registrar_auxiliar'):
                ids_string = form.cleaned_data.get('auxiliares_extras_list')
                if ids_string:
                    ids_list = [int(x) for x in ids_string.split(',') if x.strip().isdigit()]
                    obj.auxiliares_extras.set(ids_list)
                else:
                    obj.auxiliares_extras.clear()
            else:
                obj.auxiliares_extras.clear()

            messages.success(request, "Apontamento atualizado com sucesso!")
            return redirect('historico_apontamentos')
    else:
        # Preenchimento inicial do formulário para Edição
        initial_data = {}
        if apontamento.data_apontamento:
            initial_data['data_apontamento'] = apontamento.data_apontamento.strftime('%d/%m/%Y')
        if apontamento.data_dorme_fora:
            initial_data['data_dorme_fora'] = apontamento.data_dorme_fora.strftime('%d/%m/%Y')

        if apontamento.veiculo:
            initial_data['registrar_veiculo'] = True
            initial_data['veiculo_selecao'] = apontamento.veiculo.id
        elif apontamento.veiculo_manual_placa:
            initial_data['registrar_veiculo'] = True
            initial_data['veiculo_selecao'] = 'OUTRO'
            initial_data['veiculo_manual_modelo'] = apontamento.veiculo_manual_modelo
            initial_data['veiculo_manual_placa'] = apontamento.veiculo_manual_placa

        if apontamento.auxiliar:
            initial_data['registrar_auxiliar'] = True
            initial_data['auxiliar_selecao'] = apontamento.auxiliar
            
            # Recupera IDs para o campo hidden
            ids_list = list(apontamento.auxiliares_extras.values_list('id', flat=True))
            initial_data['auxiliares_extras_list'] = ",".join(map(str, ids_list))
        
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
    """Exclusão de registro (Acesso Admin)."""
    apontamento = get_object_or_404(Apontamento, pk=pk)
    apontamento.delete()
    messages.success(request, "Apontamento excluído com sucesso.")
    return redirect('historico_apontamentos')


@login_required
@user_passes_test(is_owner)
def aprovar_ajuste_view(request, pk):
    """Aprovação rápida de ajuste sem necessidade de edição."""
    apontamento = get_object_or_404(Apontamento, pk=pk)
    apontamento.status_ajuste = 'APROVADO'
    apontamento.save()
    messages.success(request, "Solicitação marcada como APROVADA.")
    return redirect('historico_apontamentos')


# ==============================================================================
# 4. APIs AJAX & UTILITÁRIOS
# ==============================================================================

@login_required
def apontamento_sucesso_view(request):
    return render(request, 'produtividade/apontamento_sucesso.html')

@login_required
def get_projeto_info_ajax(request, projeto_id):
    projeto = get_object_or_404(Projeto, pk=projeto_id)
    return JsonResponse({'nome_projeto': projeto.nome})

@login_required
def get_colaborador_info_ajax(request, colaborador_id):
    colaborador = get_object_or_404(Colaborador, pk=colaborador_id)
    return JsonResponse({'cargo': colaborador.cargo})

@login_required
def get_auxiliares_ajax(request):
    auxs = Colaborador.objects.filter(cargo__in=['AUXILIAR TECNICO', 'OFICIAL DE SISTEMAS']).values('id', 'nome_completo')
    return JsonResponse({'auxiliares': list(auxs)})

@login_required
def get_centro_custo_info_ajax(request, cc_id):
    cc = get_object_or_404(CentroCusto, pk=cc_id)
    return JsonResponse({'permite_alocacao': cc.permite_alocacao})

@login_required
def get_calendar_status_ajax(request):
    """
    Retorna o status dos dias no calendário (preenchido, dorme_fora, etc.) para feedback visual.
    """
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
    start_date = date(year, month, 1)
    end_date = date(year, month, num_days)

    queryset = Apontamento.objects.filter(
        colaborador=colaborador, data_apontamento__gte=start_date, data_apontamento__lte=end_date
    ).values('data_apontamento', 'dorme_fora')
    
    # Mapeia dias com atividades
    dias_info = {}
    for entry in queryset:
        d_str = entry['data_apontamento'].strftime('%Y-%m-%d')
        if d_str not in dias_info:
            dias_info[d_str] = entry['dorme_fora']
        else:
            if entry['dorme_fora']:
                dias_info[d_str] = True
    
    days_data = []
    today = timezone.now().date()

    for day in range(1, num_days + 1):
        current_date = date(year, month, day)
        date_str = current_date.strftime('%Y-%m-%d')
        
        status = 'missing'
        has_dorme_fora = False

        if date_str in dias_info:
            status = 'filled'
            has_dorme_fora = dias_info[date_str]
        elif current_date > today:
            status = 'future'
        
        days_data.append({
            'date': date_str, 
            'day': day, 
            'status': status,
            'has_dorme_fora': has_dorme_fora
        })

    return JsonResponse({'is_owner': False, 'days': days_data})

@csrf_exempt
def api_dashboard_data(request):
    """
    API JSON para alimentar o Dashboard externo (PHP) ou interno.
    Agora protegida por API Key, igual à exportação.
    """
    # 1. Segurança via API Key
    api_key_esperada = getattr(settings, 'DJANGO_API_KEY', 'chave_secreta_123')
    token_recebido = request.headers.get('X-API-KEY')

    # Permite acesso se tiver a chave OU se for usuário logado no navegador
    if token_recebido != api_key_esperada and not request.user.is_authenticated:
         return JsonResponse({'erro': 'Acesso Negado'}, status=403)

    # 2. Definir o range de datas (Vamos pegar dados de HOJE)
    hoje = timezone.now().date()
    
    # 3. Buscar os apontamentos
    qs = Apontamento.objects.filter(data_apontamento=hoje).select_related('projeto', 'colaborador')

    # 4. Processar métricas
    total_registros = qs.count()
    total_segundos = 0
    projetos_ativos = {}
    colaboradores_ids = set()

    for a in qs:
        # Calcular horas (Termino - Inicio)
        if a.hora_inicio and a.hora_termino:
            dummy_date = date(2000, 1, 1)
            dt_inicio = datetime.combine(dummy_date, a.hora_inicio)
            dt_termino = datetime.combine(dummy_date, a.hora_termino)
            
            # Ajuste para virada de noite
            if dt_termino < dt_inicio:
                dt_termino += timedelta(days=1)
            
            diff = dt_termino - dt_inicio
            total_segundos += diff.total_seconds()

        # Contagem por Projeto
        nome_proj = "Outros"
        if a.local_execucao == 'INT':
             if a.projeto: nome_proj = a.projeto.nome
             elif a.codigo_cliente: nome_proj = f"Cliente {a.codigo_cliente.codigo}"
        else:
             if a.centro_custo: nome_proj = a.centro_custo.nome

        projetos_ativos[nome_proj] = projetos_ativos.get(nome_proj, 0) + 1
        
        # Colaboradores únicos
        if a.colaborador:
            colaboradores_ids.add(a.colaborador.nome_completo)

    # Converter segundos para Horas decimais
    total_horas = round(total_segundos / 3600, 2)

    # 5. Montar o JSON de resposta
    data = {
        'data_referencia': hoje.strftime('%d/%m/%Y'),
        'kpis': {
            'total_apontamentos': total_registros,
            'total_horas': total_horas,
            'colaboradores_ativos': len(colaboradores_ids),
        },
        'grafico_projetos': {
            'labels': list(projetos_ativos.keys()),
            'valores': list(projetos_ativos.values())
        },
        'lista_colaboradores': list(colaboradores_ids)
    }

    return JsonResponse(data)

# ==============================================================================
# 5. RELATÓRIOS (EXPORTAÇÃO EXCEL)
# ==============================================================================

@login_required
@user_passes_test(is_owner)
def exportar_relatorio_excel(request):
    """
    Gera um relatório consolidado em Excel para conferência de folha e custos.
    """
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    queryset = Apontamento.objects.select_related(
        'projeto', 'colaborador', 'veiculo', 'centro_custo', 'codigo_cliente'
    ).prefetch_related('auxiliares_extras').all().order_by('data_apontamento')
    
    if start_date_str and end_date_str:
        try:
            start = timezone.datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end = timezone.datetime.strptime(end_date_str, '%Y-%m-%d').date()
            queryset = queryset.filter(data_apontamento__gte=start, data_apontamento__lte=end)
        except ValueError:
            pass

    # Setup do Excel
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Relatorio de Horas"

    headers = [
        "Data", "Dia Semana", "Colaborador", "Cargo", "Origem", "Tipo", 
        "Local (Obra/Setor)", "Código de Obra", "Código Cliente", 
        "Veículo", "Placa", "Hora Início", "Hora Fim", "Total Horas", 
        "Plantão", "Data Plantão", "Dorme Fora", "Data Dorme-Fora", "Observações", "Registrado Por"
    ]
    ws.append(headers)

    # Estilo do cabeçalho
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color="4F46E5", end_color="4F46E5", fill_type="solid")
        cell.alignment = Alignment(horizontal='center', vertical='center')

    def format_duration(inicio, fim):
        """Calcula a duração considerando virada de dia (ex: 22h às 02h)."""
        dummy_date = timezone.now().date()
        dt_inicio = timezone.datetime.combine(dummy_date, inicio)
        dt_fim = timezone.datetime.combine(dummy_date, fim)
        
        # LÓGICA DE CORREÇÃO PARA VIRADA DE NOITE
        if dt_fim < dt_inicio:
            dt_fim += timedelta(days=1)

        diff = dt_fim - dt_inicio
        total_seconds = int(diff.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return f"{hours:02}:{minutes:02}:{seconds:02}"

    dias_semana_pt = {
        0: 'Segunda-feira', 1: 'Terça-feira', 2: 'Quarta-feira',
        3: 'Quinta-feira', 4: 'Sexta-feira', 5: 'Sábado', 6: 'Domingo'
    }

    for item in queryset:
        data_fmt = item.data_apontamento.strftime('%d/%m/%Y')
        dia_semana = dias_semana_pt[item.data_apontamento.weekday()]
        
        # Origem
        origem = item.get_local_inicio_jornada_display()
        if item.local_inicio_jornada == 'OUT' and item.local_inicio_jornada_outros:
            origem = f"Outros - {item.local_inicio_jornada_outros}"
        if not origem: origem = "-"

        # Local
        local_nome = ""
        col_codigo_obra = ""
        col_codigo_cliente = ""
        tipo = "OBRA" if item.local_execucao == 'INT' else "EXTERNO"

        if item.local_execucao == 'INT':
            if item.projeto:
                local_nome = item.projeto.nome
                col_codigo_obra = item.projeto.codigo
            elif item.codigo_cliente:
                local_nome = item.codigo_cliente.nome
                col_codigo_cliente = item.codigo_cliente.codigo
        else:
            local_nome = item.centro_custo.nome if item.centro_custo else "Externo"
            if item.projeto: col_codigo_obra = item.projeto.codigo
            elif item.codigo_cliente: col_codigo_cliente = item.codigo_cliente.codigo

        if col_codigo_obra and len(col_codigo_obra) >= 5:
             col_codigo_cliente = col_codigo_obra[1:5]
        elif col_codigo_obra:
             col_codigo_cliente = col_codigo_obra

        # Veículo
        veiculo_nome_modelo = ""
        veiculo_placa_only = ""

        if item.veiculo:
            veiculo_nome_modelo = item.veiculo.descricao if item.veiculo.descricao else "Veículo da Frota"
            veiculo_placa_only = item.veiculo.placa
        elif item.veiculo_manual_modelo:
            veiculo_nome_modelo = item.veiculo_manual_modelo
            veiculo_placa_only = item.veiculo_manual_placa if item.veiculo_manual_placa else ""

        duracao_str = format_duration(item.hora_inicio, item.hora_termino)
        reg_por = item.registrado_por.username if item.registrado_por else "Sistema"

        plantao_str = "SIM" if item.em_plantao else "NÃO"
        data_plantao_str = item.data_plantao.strftime('%d/%m/%Y') if item.data_plantao else "-"
        dorme_fora_str = "SIM" if item.dorme_fora else "NÃO"
        data_dorme_fora_str = item.data_dorme_fora.strftime('%d/%m/%Y') if item.data_dorme_fora else "-"

        # Linha Principal
        row_principal = [
            data_fmt, dia_semana, item.colaborador.nome_completo, item.colaborador.cargo,
            origem, tipo, local_nome, col_codigo_obra, col_codigo_cliente, 
            veiculo_nome_modelo, veiculo_placa_only, item.hora_inicio, item.hora_termino, 
            duracao_str, plantao_str, data_plantao_str, dorme_fora_str, data_dorme_fora_str, 
            item.ocorrencias, reg_por
        ]
        ws.append(row_principal)

        # Linhas Auxiliares (Carona)
        auxiliares = []
        if item.auxiliar:
            auxiliares.append(item.auxiliar)
        
        # Correção: Acesso direto ao manager ManyToMany ao invés de atributo inexistente
        extras = list(item.auxiliares_extras.all())
        auxiliares.extend(extras)

        for aux in auxiliares:
            row_aux = [
                data_fmt, dia_semana, aux.nome_completo, aux.cargo,
                origem, tipo, local_nome, col_codigo_obra, col_codigo_cliente, 
                "Carona", "", item.hora_inicio, item.hora_termino, 
                duracao_str, plantao_str, data_plantao_str, dorme_fora_str, data_dorme_fora_str, 
                f"Auxiliar de: {item.colaborador.nome_completo}", reg_por
            ]
            ws.append(row_aux)

    # Auto-ajuste de largura das colunas
    for col in ws.columns:
        max_length = 0
        column = col[0].column_letter
        for cell in col:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except: pass
        adjusted_width = (max_length + 2)
        ws.column_dimensions[column].width = adjusted_width

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    filename = f"Relatorio_Horas_{timezone.now().strftime('%Y%m%d_%H%M')}.xlsx"
    response['Content-Disposition'] = f'attachment; filename={filename}'
    
    wb.save(response)
    return response


@csrf_exempt
def api_exportar_json(request):
    api_key_esperada = getattr(settings, 'DJANGO_API_KEY', 'chave_secreta_123')
    token_recebido = request.headers.get('X-API-KEY')
    if token_recebido != api_key_esperada: return JsonResponse({'erro': 'Acesso Negado'}, status=403)

    days = int(request.GET.get('days', 45))
    start_date = timezone.now().date() - timedelta(days=days)
    
    queryset = Apontamento.objects.select_related(
        'projeto', 'colaborador', 'veiculo', 'centro_custo', 'codigo_cliente'
    ).prefetch_related('auxiliares_extras').filter(
        data_apontamento__gte=start_date
    ).order_by('data_apontamento')

    dados_saida = []

    def fmt_hora(h): return h.strftime('%H:%M:%S') if h else None
    def fmt_data(d): return d.strftime('%Y-%m-%d') if d else None

    for item in queryset:
        local_nome = ""
        codigo_obra = None
        codigo_cliente = None
        
        if item.local_execucao == 'INT':
            if item.projeto:
                local_nome = item.projeto.nome
                codigo_obra = item.projeto.codigo
            elif item.codigo_cliente:
                local_nome = item.codigo_cliente.nome
                codigo_cliente = item.codigo_cliente.codigo
        else:
            local_nome = item.centro_custo.nome if item.centro_custo else "Externo"
            if item.projeto: codigo_obra = item.projeto.codigo
            elif item.codigo_cliente: codigo_cliente = item.codigo_cliente.codigo

        if codigo_obra and len(str(codigo_obra)) >= 5:
             if not codigo_cliente: codigo_cliente = str(codigo_obra)[1:5]
        elif codigo_obra and not codigo_cliente:
             codigo_cliente = codigo_obra

        veiculo_nome = ""
        placa = ""
        if item.veiculo:
            veiculo_nome = item.veiculo.descricao
            placa = item.veiculo.placa
        elif item.veiculo_manual_modelo:
            veiculo_nome = item.veiculo_manual_modelo
            placa = item.veiculo_manual_placa

        base_obj = {
            'data': fmt_data(item.data_apontamento),
            'dia_semana': item.data_apontamento.weekday(), 
            'origem': item.get_local_inicio_jornada_display(),
            'tipo': 'OBRA' if item.local_execucao == 'INT' else 'EXTERNO',
            'local': local_nome,
            'codigo_obra': codigo_obra,
            'codigo_cliente': codigo_cliente,
            'hora_inicio': fmt_hora(item.hora_inicio),
            'hora_fim': fmt_hora(item.hora_termino), 
            'observacoes': item.ocorrencias,
            'registrado_por': item.registrado_por.username if item.registrado_por else 'Sistema',
            'dorme_fora': item.dorme_fora,
            'em_plantao': item.em_plantao,
            'status': item.status_ajuste or 'OK'
        }

        row_main = base_obj.copy()
        row_main.update({
            'colaborador': item.colaborador.nome_completo,
            'cargo': item.colaborador.cargo,
            'veiculo': veiculo_nome,
            'placa': placa,
            'is_auxiliar': False
        })
        dados_saida.append(row_main)

        auxiliares = []
        if item.auxiliar: auxiliares.append(item.auxiliar)
        auxiliares.extend(list(item.auxiliares_extras.all()))

        for aux in auxiliares:
            row_aux = base_obj.copy()
            row_aux.update({
                'colaborador': aux.nome_completo,
                'cargo': aux.cargo,
                'veiculo': 'Carona', 
                'placa': None,
                'is_auxiliar': True,
                # Auxiliares herdam o status do apontamento principal, 
                # mas geralmente não ganham plantão/dorme fora automaticamente (regra de negócio),
                # vamos manter false para evitar duplicidade de custo visual, ou true se a regra for essa.
                # Vou manter FALSE para caronas por segurança.
                'dorme_fora': True if item.dorme_fora else False, 
                'em_plantao': True if item.em_plantao else False, 
            })
            dados_saida.append(row_aux)

    return JsonResponse(dados_saida, safe=False)