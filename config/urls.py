"""
URL configuration for config project.
...
"""
from django.contrib import admin
from django.urls import path, include
from produtividade import views as produtividade_views # 🚨 Importar views do seu app

urlpatterns = [
    path('', produtividade_views.home_redirect_view, name='home'),
    
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')), 
    path('produtividade/', include('produtividade.urls')),
]