from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.contrib import messages
from django.db.models import Q
from .forms import ApontamentoForm
from .models import Apontamento, Projeto, Colaborador, Setor, Veiculo, CodigoCliente
from django.contrib.auth.models import Group

# ==============================================================================
# LÓGICA DE CONTROLE DE ACESSO (RBAC)
# ==============================================================================

def is_user_in_group(user, group_name):
    return user.groups.filter(name=group_name).exists()

def is_owner(user):
    return user.is_superuser

def is_admin_or_gestor(user):
    # Verifica se é Gestor ou Administrativo (mas não Owner)
    return is_user_in_group(user, 'GESTOR') or is_user_in_group(user, 'ADMINISTRATIVO')

def is_operacional(user):
    # Se não for Owner, nem Gestor, nem Admin, assume Operacional
    return user.is_authenticated and not is_owner(user) and not is_admin_or_gestor(user)

@login_required
def home_redirect_view(request):
    return redirect('historico_apontamentos')

# ==============================================================================
# VIEWS DE OPERAÇÃO (CRIAR, EDITAR, EXCLUIR)
# ==============================================================================

@login_required
def apontamento_atividade_view(request):
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

            # --- Tratamento de Veículo ---
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
        form = ApontamentoForm(**user_kwargs)

    context = {
        'form': form,
        'titulo': 'Timesheet',
        'subtitulo': 'Preencha os dados de horário e local do colaborador.',
        'is_editing': False
    }
    return render(request, 'produtividade/apontamento_form.html', context)


@login_required
@user_passes_test(is_owner) # Apenas OWNER pode editar
def editar_apontamento_view(request, pk):
    apontamento = get_object_or_404(Apontamento, pk=pk)
    user_kwargs = {'user': request.user, 'instance': apontamento}

    if request.method == 'POST':
        form = ApontamentoForm(request.POST, **user_kwargs)
        if form.is_valid():
            # A lógica de clean() e save() do form já trata a maioria dos campos
            obj = form.save(commit=False)
            
            # Reforça lógica de limpeza manual se necessário (igual ao create)
            if not form.cleaned_data.get('registrar_auxiliar'):
                obj.auxiliar = None
                obj.auxiliares_extras_ids = None
            
            # (Lógica de veículo já está no clean do form ou pode ser reforçada aqui)
            
            obj.save()
            messages.success(request, "Apontamento atualizado com sucesso!")
            return redirect('historico_apontamentos')
    else:
        # Prepara dados iniciais para checkboxes e campos ocultos
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
@user_passes_test(is_owner) # Apenas OWNER pode excluir
def excluir_apontamento_view(request, pk):
    apontamento = get_object_or_404(Apontamento, pk=pk)
    apontamento.delete()
    messages.success(request, "Apontamento excluído com sucesso.")
    return redirect('historico_apontamentos')


# ==============================================================================
# VIEW DE HISTÓRICO (COM FILTROS AVANÇADOS)
# ==============================================================================

@login_required
def historico_apontamentos_view(request):
    user = request.user
    queryset = Apontamento.objects.all()

    # 1. Recupera o colaborador logado (se houver)
    try:
        colaborador_logado = Colaborador.objects.get(user_account=user)
    except Colaborador.DoesNotExist:
        colaborador_logado = None

    # 2. Aplica Filtros baseados no Perfil
    if is_owner(user):
        # OWNER: Vê tudo
        pass 
        
    elif is_admin_or_gestor(user) and colaborador_logado:
        # ADMIN/GESTOR: Vê colaboradores dos setores que gerencia + o que ele próprio registrou
        setores_gerenciados = colaborador_logado.setores_gerenciados.all()
        
        if setores_gerenciados.exists():
            queryset = queryset.filter(
                Q(colaborador__setor__in=setores_gerenciados) | 
                Q(registrado_por=user)
            )
        else:
            # Se não tiver setores configurados, vê apenas seus registros
            queryset = queryset.filter(registrado_por=user)
            
    else:
        # OPERACIONAL (ou sem perfil definido): Vê apenas o que registrou
        queryset = queryset.filter(registrado_por=user)

    # --- Prepara Lista para Exibição ---
    apontamentos_db = queryset.order_by('-data_apontamento', '-id')
    historico_lista = []

    for item in apontamentos_db:
        # Local Ref
        if item.local_execucao == 'INT':
            if item.projeto:
                p_cod = item.projeto.codigo if item.projeto.codigo else ""
                local_ref = f"{p_cod} - {item.projeto.nome}" if p_cod else f"OBRA: {item.projeto.nome}"
            elif item.codigo_cliente:
                local_ref = f"{item.codigo_cliente.codigo} - {item.codigo_cliente.nome}"
            else:
                local_ref = "Obra/Cliente não informado"
        else:
            local_ref = item.setor.nome if item.setor else "Setor não informado"

        # Veículo Display
        if item.veiculo:
            veiculo_display = str(item.veiculo)
        elif item.veiculo_manual_placa:
            veiculo_display = f"{item.veiculo_manual_modelo} - {item.veiculo_manual_placa} (Externo)"
        else:
            veiculo_display = ""

        # User Display
        reg_user = item.registrado_por
        if reg_user:
            if reg_user.first_name:
                user_display = f"{reg_user.first_name} {reg_user.last_name}".strip()
                u_first = reg_user.first_name
                u_last = reg_user.last_name
            else:
                user_display = reg_user.username
                u_first = reg_user.username
                u_last = ""
        else:
            user_display = "Sistema"; u_first = "-"; u_last = ""

        base_dict = {
            'id': item.id, # Essencial para link de edição
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
            'user_first': u_first,
            'user_last': u_last
        }

        # Linha Principal
        row_main = base_dict.copy()
        row_main.update({
            'nome': item.colaborador.nome_completo,
            'cargo': item.colaborador.cargo,
            'veiculo': veiculo_display,
            'is_auxiliar': False
        })
        historico_lista.append(row_main)

        # Auxiliares (Explode linhas)
        auxiliares_a_exibir = []
        if item.auxiliar: auxiliares_a_exibir.append(item.auxiliar)
        if item.auxiliares_extras_ids:
            try:
                ids = [int(x) for x in item.auxiliares_extras_ids.split(',') if x.strip()]
                extras = Colaborador.objects.filter(id__in=ids)
                auxiliares_a_exibir.extend(extras)
            except ValueError: pass

        for aux in auxiliares_a_exibir:
            row_aux = base_dict.copy()
            row_aux.update({
                'nome': aux.nome_completo,
                'cargo': aux.cargo,
                'veiculo': "", 
                'is_auxiliar': True
            })
            historico_lista.append(row_aux)

    context = {
        'titulo': "Histórico",
        'apontamentos_lista': historico_lista,
        'show_user_column': not is_operacional(user), # Operacional não precisa ver quem registrou (foi ele mesmo)
        'is_owner': is_owner(user) # Flag para exibir botões de editar/excluir no template
    }
    return render(request, 'produtividade/historico_apontamentos.html', context)


# ==============================================================================
# APIS AJAX & UTILITÁRIOS
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
    lista = [{'id': c['id'], 'nome': c['nome_completo']} for c in auxs]
    return JsonResponse({'auxiliares': lista})

@login_required
def home_view(request):
    return render(request, 'produtividade/home.html')