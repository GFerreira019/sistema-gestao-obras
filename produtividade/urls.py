from django.urls import path
from . import views

app_name = 'produtividade'

urlpatterns = [
    # ==========================================================================
    # NAVEGAÇÃO BÁSICA
    # ==========================================================================
    path('', views.home_redirect_view, name='home'),
    path('menu/', views.home_view, name='home_menu'),
    path('configuracoes/', views.configuracoes_view, name='configuracoes'),

    # ==========================================================================
    # CORE: APONTAMENTOS (CRUD)
    # ==========================================================================
    # Formulário de Criação
    path('apontamento/novo/', views.apontamento_atividade_view, name='novo_apontamento'),
    
    # Tela de feedback de sucesso
    path('apontamento/sucesso/', views.apontamento_sucesso_view, name='apontamento_sucesso'),

    # Funcionalidades de Edição e Exclusão (Admin/Gestor)
    path('apontamento/editar/<int:pk>/', views.editar_apontamento_view, name='editar_apontamento'),
    path('apontamento/excluir/<int:pk>/', views.excluir_apontamento_view, name='excluir_apontamento'),

    # ==========================================================================
    # HISTÓRICO E FLUXOS DE APROVAÇÃO
    # ==========================================================================
    path('historico/', views.historico_apontamentos_view, name='historico_apontamentos'),

    # Solicitar Ajuste (Usuário/Colaborador pede correção em registro passado)
    path('apontamento/<int:pk>/solicitar-ajuste/', views.solicitar_ajuste_view, name='solicitar_ajuste'),

    # Aprovar Ajuste (Gestor aceita a correção)
    path('apontamento/<int:pk>/aprovar-ajuste/', views.aprovar_ajuste_view, name='aprovar_ajuste'),

    # ==========================================================================
    # FLUXO DE APROVAÇÃO (GERENTE)
    # ==========================================================================
    path('aprovacoes/', views.aprovacao_dashboard_view, name='aprovacao_dashboard'),
    path('aprovacoes/<int:pk>/analise/', views.analise_apontamento_view, name='analise_apontamento'),
    path('aprovacoes/<int:pk>/processar/', views.processar_aprovacao_view, name='processar_aprovacao'),

    # ==========================================================================
    # APIs AJAX
    # ==========================================================================
    path('api/get-projeto-info/<int:projeto_id>/', views.get_projeto_info_ajax, name='get_projeto_info'),
    path('api/get-colaborador-info/<int:colaborador_id>/', views.get_colaborador_info_ajax, name='get_colaborador_info'),
    path('api/get-auxiliares/', views.get_auxiliares_ajax, name='get_auxiliares'), 
    path('api/get-centro-custo-info/<int:cc_id>/', views.get_centro_custo_info_ajax, name='get_centro_custo_info_ajax'),
    path('api/get-calendar-status/', views.get_calendar_status_ajax, name='get_calendar_status_ajax'),

    # ==========================================================================
    # INTEGRAÇÃO EXTERNA (Dashboard PHP)
    # ==========================================================================
    # 1. Status Online/Offline e Gráficos de hoje
    path('api/dashboard/', views.api_dashboard_data, name='api_dashboard_data'),
    
    # 2. Sincronização completa de dados (Excel JSON)
    path('api/exportar-completo/', views.api_exportar_json, name='api_exportar_completo'),

    # ==========================================================================
    # RELATÓRIOS E EXPORTAÇÃO
    # ==========================================================================
    path('exportar/excel/', views.exportar_relatorio_excel, name='exportar_relatorio_excel'),
]