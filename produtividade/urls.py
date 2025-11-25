from django.urls import path
from . import views

urlpatterns = [
    # Redireciona para o novo apontamento
    path('', views.home_redirect_view, name='home'),

    # Formulário Principal
    path('apontamento/novo/', views.apontamento_atividade_view, name='novo_apontamento'),

    # Tela de Sucesso
    path('apontamento/sucesso/', views.apontamento_sucesso_view, name='apontamento_sucesso'),
    
    # Histórico
    path('historico/', views.historico_apontamentos_view, name='historico_apontamentos'),
    
    # APIs AJAX
    path('api/get-projeto-info/<int:projeto_id>/', views.get_projeto_info_ajax, name='get_projeto_info'),
    path('api/get-colaborador-info/<int:colaborador_id>/', views.get_colaborador_info_ajax, name='get_colaborador_info'),
    path('api/get-auxiliares/', views.get_auxiliares_ajax, name='get_auxiliares'), 
]