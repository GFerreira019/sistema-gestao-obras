"""
URL configuration for config project.
...
"""
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from produtividade import views as produtividade_views

urlpatterns = [
    path('', produtividade_views.home_redirect_view, name='home'),
    path('', include('produtividade.urls')),
    
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')), 
    path('produtividade/', include('produtividade.urls')),
    path('accounts/', include('django.contrib.auth.urls')),
]