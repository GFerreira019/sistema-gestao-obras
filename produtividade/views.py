from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.contrib import messages
from .forms import ApontamentoForm
from .models import Apontamento, Projeto, Colaborador, Setor, Veiculo

# ==============================================================================
# LÓGICA DE CONTROLE DE ACESSO E UTILITÁRIOS
# ==============================================================================

def is_gestor(user):
    """
    Verifica se o usuário tem permissão de gestor.
    Retorna True se for superusuário ou pertencer ao grupo 'Gestor'.
    """
    return user.groups.filter(name='Gestor').exists() or user.is_superuser


@login_required
def home_redirect_view(request):
    """
    Redirecionamento inteligente após login.
    Gestores vão para o Histórico; Operadores vão para o Formulário de Novo Apontamento.
    """
    if is_gestor(request.user):
        return redirect('historico_apontamentos')
    else:
        return redirect('novo_apontamento')


# ==============================================================================
# VIEWS PRINCIPAIS (CRUD E TELAS)
# ==============================================================================

@login_required
def apontamento_atividade_view(request):
    """
    Formulário principal de registro de ponto/atividade.
    Processa o envio de dados, incluindo lógica para veículos manuais e auxiliares.
    """
    if request.method == 'POST':
        form = ApontamentoForm(request.POST)
        
        if form.is_valid():
            # Cria instância do objeto, mas não salva no banco ainda
            apontamento = form.save(commit=False)
            apontamento.registrado_por = request.user
            
            # --- Processamento de Auxiliares ---
            # Salva explicitamente os auxiliares selecionados
            if form.cleaned_data.get('registrar_auxiliar'):
                apontamento.auxiliar = form.cleaned_data.get('auxiliar_selecao')
                apontamento.auxiliares_extras_ids = form.cleaned_data.get('auxiliares_extras_list')
            else:
                apontamento.auxiliar = None
                apontamento.auxiliares_extras_ids = None

            # --- Processamento de Veículo (Lógica Híbrida) ---
            if form.cleaned_data.get('registrar_veiculo'):
                selection = form.cleaned_data.get('veiculo_selecao')
                
                if selection == 'OUTRO':
                    # Veículo Manual: Deixa a FK vazia e usa os campos manuais (já populados pelo form)
                    apontamento.veiculo = None
                else:
                    # Veículo da Frota: Busca o objeto e limpa os campos manuais
                    try:
                        apontamento.veiculo = Veiculo.objects.get(pk=selection)
                        apontamento.veiculo_manual_modelo = None
                        apontamento.veiculo_manual_placa = None
                    except Veiculo.DoesNotExist:
                        apontamento.veiculo = None
            else:
                # Nenhum veículo utilizado
                apontamento.veiculo = None
                apontamento.veiculo_manual_modelo = None
                apontamento.veiculo_manual_placa = None

            # Salva o registro final no banco
            apontamento.save()
            
            # Feedback visual e reset do formulário
            messages.success(request, f"Registro de {apontamento.colaborador} salvo com sucesso!")
            return redirect('novo_apontamento')
    else:
        form = ApontamentoForm()

    context = {
        'form': form,
        'titulo': 'Registro de Ponto',
        'subtitulo': 'Preencha os dados de horário e local do colaborador.'
    }
    return render(request, 'produtividade/apontamento_form.html', context)


@login_required
@user_passes_test(is_gestor, login_url='/')
def historico_apontamentos_view(request):
    """
    Exibe o histórico de apontamentos.
    Realiza o processamento para 'explodir' os registros de auxiliares,
    criando linhas visuais separadas na tabela para cada membro da equipe.
    """
    apontamentos_db = Apontamento.objects.all().order_by('-data_apontamento', '-id')
    historico_lista = []

    for item in apontamentos_db:
        # Define a referência de local (Obra ou Setor)
        if item.local_execucao == 'INT':
            local_ref = item.projeto.nome if item.projeto else "Obra não informada"
        else:
            local_ref = item.setor.nome if item.setor else "Setor não informado"

        # Formata a exibição do veículo (Frota ou Manual)
        if item.veiculo:
            veiculo_display = str(item.veiculo)
        elif item.veiculo_manual_placa:
            veiculo_display = f"{item.veiculo_manual_modelo} - {item.veiculo_manual_placa} (Externo)"
        else:
            veiculo_display = ""

        # Dados base comuns a todas as linhas deste registro
        base_dict = {
            'data': item.data_apontamento,
            'local_ref': local_ref,
            'inicio': item.hora_inicio,
            'termino': item.hora_termino,
            'local_tipo': item.get_local_execucao_display(),
            'obs': item.ocorrencias,
            'tangerino': item.local_inicio_jornada,
            'tangerino_obs': item.local_inicio_jornada_outros,
        }

        # 1. Linha do Colaborador Principal
        row_main = base_dict.copy()
        row_main.update({
            'nome': item.colaborador.nome_completo,
            'cargo': item.colaborador.cargo,
            'veiculo': veiculo_display, # Veículo aparece apenas para o motorista
            'is_auxiliar': False
        })
        historico_lista.append(row_main)

        # 2. Linha do Auxiliar Principal (se houver)
        if item.auxiliar:
            row_aux = base_dict.copy()
            row_aux.update({
                'nome': item.auxiliar.nome_completo,
                'cargo': item.auxiliar.cargo,
                'veiculo': "", 
                'is_auxiliar': True
            })
            historico_lista.append(row_aux)

        # 3. Linhas dos Auxiliares Extras (se houver)
        if item.auxiliares_extras_ids:
            try:
                ids = [int(x) for x in item.auxiliares_extras_ids.split(',') if x.strip()]
                extras = Colaborador.objects.filter(id__in=ids)
                for extra in extras:
                    row_extra = base_dict.copy()
                    row_extra.update({
                        'nome': extra.nome_completo,
                        'cargo': extra.cargo,
                        'veiculo': "",
                        'is_auxiliar': True
                    })
                    historico_lista.append(row_extra)
            except ValueError:
                pass # Ignora erros de formatação na lista de IDs

    context = {
        'titulo': "Apontamentos do Timesheet",
        'apontamentos_lista': historico_lista
    }
    return render(request, 'produtividade/historico_apontamentos.html', context)


@login_required
def apontamento_sucesso_view(request):
    """Página simples de sucesso (opcional, pois usamos toast messages agora)."""
    return render(request, 'produtividade/apontamento_sucesso.html')


# ==============================================================================
# API ENDPOINTS (AJAX/JSON)
# Utilizados pelo JavaScript do frontend para carregamento dinâmico de dados
# ==============================================================================

@login_required
def get_projeto_info_ajax(request, projeto_id):
    """Retorna o nome do projeto dado seu ID."""
    projeto = get_object_or_404(Projeto, pk=projeto_id)
    return JsonResponse({'nome_projeto': projeto.nome})


@login_required
def get_colaborador_info_ajax(request, colaborador_id):
    """Retorna o cargo do colaborador dado seu ID."""
    colaborador = get_object_or_404(Colaborador, pk=colaborador_id)
    return JsonResponse({'cargo': colaborador.cargo})


@login_required
def get_auxiliares_ajax(request):
    """
    Retorna lista de colaboradores elegíveis para serem auxiliares.
    Filtra por cargos específicos: Auxiliar Técnico e Oficial de Sistemas.
    """
    auxs = Colaborador.objects.filter(
        cargo__in=['AUXILIAR TECNICO', 'OFICIAL DE SISTEMAS']
    ).values('id', 'nome_completo')
    
    # Formata lista para consumo fácil no JS
    lista = [{'id': c['id'], 'nome': c['nome_completo']} for c in auxs]
    
    return JsonResponse({'auxiliares': lista})