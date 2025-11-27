from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from .models import Apontamento, Colaborador, Veiculo, Projeto, Setor, CodigoCliente

class ApontamentoForm(forms.ModelForm):
    """
    Formulário principal para registro de apontamentos de produtividade.
    
    Funcionalidades:
    - Gerencia lógica condicional para Veículos (Frota vs Manual).
    - Gerencia Auxiliares (Principal + Extras).
    - Adapta campos com base no Local de Trabalho (Obra vs Setor).
    - Implementa controle de acesso (RBAC) bloqueando campos para usuários Operacionais.
    """

    # ==========================================================================
    # CAMPOS VISUAIS E READ-ONLY
    # ==========================================================================
    codigo_cliente = forms.ModelChoiceField(
        queryset=CodigoCliente.objects.filter(ativo=True),
        required=False,
        label="Código do Cliente",
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    cargo_colaborador = forms.CharField(
        required=False, 
        disabled=True, 
        label="Cargo", 
        initial="-"
    )

    # ==========================================================================
    # GESTÃO DE VEÍCULOS
    # ==========================================================================
    registrar_veiculo = forms.BooleanField(
        required=False, 
        label="Adicionar veículo"
    )
    
    veiculo_selecao = forms.ChoiceField(
        required=False, 
        label="Selecione o Veículo",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    # Campos para cadastro manual (se veiculo_selecao == 'OUTRO')
    veiculo_manual_modelo = forms.CharField(
        required=False, 
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Ex: Fiat Strada'
        })
    )
    veiculo_manual_placa = forms.CharField(
        required=False, 
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'ABC1234', 
            'maxlength': '7', 
            'style': 'text-transform:uppercase'
        })
    )

    # ==========================================================================
    # GESTÃO DE AUXILIARES
    # ==========================================================================
    registrar_auxiliar = forms.BooleanField(
        required=False, 
        label="Adicionar Auxiliares?"
    )
    
    # Filtra colaboradores elegíveis para serem auxiliares
    auxiliar_selecao = forms.ModelChoiceField(
        queryset=Colaborador.objects.filter(
            cargo__in=['AUXILIAR TECNICO', 'OFICIAL DE SISTEMAS']
        ), 
        required=False, 
        label="Auxiliar Principal"
    )
    
    # Campo oculto preenchido via JavaScript com IDs dos auxiliares extras
    auxiliares_extras_list = forms.CharField(
        required=False, 
        widget=forms.HiddenInput()
    )

    class Meta:
        model = Apontamento
        fields = [
            'colaborador', 'data_apontamento', 'local_execucao',
            'projeto', 'codigo_cliente', 'local_inicio_jornada', 'local_inicio_jornada_outros',
            'setor', 'hora_inicio', 'hora_termino', 'ocorrencias',
            # Campos manuais precisam estar aqui para salvamento automático
            'veiculo_manual_modelo', 'veiculo_manual_placa'
        ]
        widgets = {
            'data_apontamento': forms.DateInput(attrs={'type': 'date'}),
            'hora_inicio': forms.TimeInput(attrs={'type': 'time'}),
            'hora_termino': forms.TimeInput(attrs={'type': 'time'}),
            'ocorrencias': forms.Textarea(attrs={'rows': 3}),
            'local_execucao': forms.Select(attrs={'class': 'form-select'}),
            'local_inicio_jornada': forms.RadioSelect(), 
            'local_inicio_jornada_outros': forms.TextInput(attrs={
                'placeholder': 'Especifique o local...', 
                'class': 'form-control'
            }),
        }

    def __init__(self, *args, **kwargs):
        """
        Sobrescreve o init para aplicar lógica de acesso baseada no Perfil (Owner, Admin, Gestor, Operacional).
        """
        self.user = kwargs.pop('user', None)
        
        super().__init__(*args, **kwargs)
        
        # --- Filtros Iniciais ---
        self.fields['projeto'].queryset = Projeto.objects.filter(ativo=True)
        self.fields['setor'].queryset = Setor.objects.filter(ativo=True)
        self.fields['codigo_cliente'].queryset = CodigoCliente.objects.filter(ativo=True)
        
        # --- Popula Campo de Veículo (Híbrido) ---
        veiculos_db = Veiculo.objects.all()
        choices = [('', '-- Escolha o Veículo --')]
        choices += [(v.id, str(v)) for v in veiculos_db]
        choices.append(('OUTRO', 'OUTRO (Cadastrar Novo)'))
        self.fields['veiculo_selecao'].choices = choices

        # --- Limpeza de Opções do Tangerino ---
        choices_tang = list(self.fields['local_inicio_jornada'].choices)
        self.fields['local_inicio_jornada'].choices = [c for c in choices_tang if c[0] != '']

        # ==============================================================================
        # LÓGICA DE ACESSO AO CAMPO 'COLABORADOR' (RBAC)
        # ==============================================================================
        if self.user:
            is_owner = self.user.is_superuser
            is_gestor = self.user.groups.filter(name='GESTOR').exists()
            is_admin = self.user.groups.filter(name='ADMINISTRATIVO').exists() # Novo Grupo
            
            # --- 1. OWNER (Vê tudo) ---
            if is_owner:
                self.fields['colaborador'].queryset = Colaborador.objects.all()
            
            # --- 2. GESTOR ou ADMINISTRATIVO (Vê setores gerenciados + o próprio) ---
            elif is_gestor or is_admin:
                try:
                    colaborador_logado = Colaborador.objects.get(user_account=self.user)
                    
                    # Pega os setores que ele gerencia (campo ManyToMany que criamos)
                    setores_permitidos = colaborador_logado.setores_gerenciados.all()
                    
                    # Se ele gerencia setores, mostra colaboradores desses setores
                    if setores_permitidos.exists():
                        qs = Colaborador.objects.filter(setor__in=setores_permitidos)
                        # Inclui a si mesmo na lista caso não esteja no setor que gerencia
                        qs = qs | Colaborador.objects.filter(pk=colaborador_logado.pk)
                        self.fields['colaborador'].queryset = qs.distinct()
                    else:
                        # Se não tiver setores configurados, vê apenas a si mesmo (fallback)
                        self.fields['colaborador'].queryset = Colaborador.objects.filter(pk=colaborador_logado.pk)
                        self.initial['colaborador'] = colaborador_logado
                        self.initial['cargo_colaborador'] = colaborador_logado.cargo
                
                except Colaborador.DoesNotExist:
                    # Se usuário tem login mas não tem cadastro de Colaborador vinculado
                    self.fields['colaborador'].queryset = Colaborador.objects.none()

            # --- 3. OPERACIONAL (Vê apenas a si mesmo) ---
            else:
                try:
                    colaborador_logado = Colaborador.objects.get(user_account=self.user)
                    
                    # Trava o campo e pré-seleciona
                    self.initial['colaborador'] = colaborador_logado
                    self.initial['cargo_colaborador'] = colaborador_logado.cargo

                    # Aplica bloqueio visual
                    self.fields['colaborador'].widget.attrs.update({
                        'class': 'form-control pointer-events-none bg-slate-700 text-gray-400 cursor-not-allowed',
                        'tabindex': '-1'
                    })
                    
                    self.fields['colaborador'].queryset = Colaborador.objects.filter(pk=colaborador_logado.pk)
                    self.fields['colaborador'].empty_label = None 
                    
                except Colaborador.DoesNotExist:
                    self.fields['colaborador'].queryset = Colaborador.objects.none()

        # Define obrigatoriedade
        self.fields['colaborador'].required = True
        self.fields['hora_inicio'].required = True
        self.fields['hora_termino'].required = True

        # CSS Padrão
        for name, field in self.fields.items():
            if name not in ['registrar_veiculo', 'registrar_auxiliar', 'local_inicio_jornada']:
                if 'class' not in field.widget.attrs:
                    field.widget.attrs.update({'class': 'form-control'})
                elif 'form-control' not in field.widget.attrs['class']:
                     field.widget.attrs['class'] += ' form-control'

    def clean(self):
        """
        Validação cruzada de campos dependentes (Local, Veículo, Horários).
        """
        cleaned_data = super().clean()
        
        # --- 1. Validação de Local (Obra vs Setor) ---
        local = cleaned_data.get('local_execucao')
        projeto = cleaned_data.get('projeto')
        cod_cliente = cleaned_data.get('codigo_cliente')
        setor = cleaned_data.get('setor')
        tangerino = cleaned_data.get('local_inicio_jornada')
        tangerino_obs = cleaned_data.get('local_inicio_jornada_outros')

        if local == 'INT': # Dentro da Obra
            # Lógica de Exclusividade: Não pode ter ambos
            if projeto and cod_cliente:
                self.add_error('projeto', "Selecione apenas o Código da Obra ou o Código do Cliente, não ambos.")
                self.add_error('codigo_cliente', "Selecione apenas o Código da Obra ou o Código do Cliente, não ambos.")
            
            # Lógica de Obrigatoriedade: Tem que ter pelo menos um
            if not projeto and not cod_cliente:
                self.add_error('projeto', "Se não houver Obra Específica, selecione o Código do Cliente.")
                self.add_error('codigo_cliente', "Se não houver Obra Específica, selecione o Código do Cliente.")

            cleaned_data['setor'] = None
            
            # Validação Tangerino
            if tangerino == 'OUT' and not tangerino_obs:
                self.add_error('local_inicio_jornada_outros', "Especifique o local para 'Outros'.")
            
            if tangerino != 'OUT': 
                cleaned_data['local_inicio_jornada_outros'] = ""
                
        elif local == 'EXT': # Fora da Obra
            if not setor:
                self.add_error('setor', "Selecione o Setor.")
            # Limpa campos de obra e cliente
            cleaned_data['projeto'] = None
            cleaned_data['codigo_cliente'] = None
            cleaned_data['local_inicio_jornada'] = None
            self.instance.projeto = None
            self.instance.codigo_cliente = None

        # --- 2. Validação de Horário ---
        inicio = cleaned_data.get('hora_inicio')
        termino = cleaned_data.get('hora_termino')
        
        if inicio and termino and termino <= inicio:
            self.add_error('hora_termino', "Hora de término deve ser maior que a inicial.")

        # --- 3. Validação de Veículo ---
        if cleaned_data.get('registrar_veiculo'):
            selection = cleaned_data.get('veiculo_selecao')
            
            if not selection:
                self.add_error('veiculo_selecao', "Selecione um veículo.")
            
            elif selection == 'OUTRO':
                # Validação para veículo manual
                mod = cleaned_data.get('veiculo_manual_modelo')
                pla = cleaned_data.get('veiculo_manual_placa')
                
                if not mod: self.add_error('veiculo_manual_modelo', "Informe o Modelo.")
                if not pla: self.add_error('veiculo_manual_placa', "Informe a Placa.")
                
                if pla:
                    # Normaliza placa
                    pla = pla.upper().replace('-', '').replace(' ', '')
                    if len(pla) != 7:
                        self.add_error('veiculo_manual_placa', "A placa deve ter 7 caracteres.")
                    cleaned_data['veiculo_manual_placa'] = pla
            else:
                # Limpa campos manuais se escolheu veículo da lista
                cleaned_data['veiculo_manual_modelo'] = None
                cleaned_data['veiculo_manual_placa'] = None
        else:
            # Limpa tudo se desmarcou veículo
            self.instance.veiculo = None
            cleaned_data['veiculo_manual_modelo'] = None
            cleaned_data['veiculo_manual_placa'] = None

        # --- 4. Validação de Auxiliares ---
        if cleaned_data.get('registrar_auxiliar'):
            if not cleaned_data.get('auxiliar_selecao'):
                self.add_error('auxiliar_selecao', "Selecione o Auxiliar.")
            
            # Prepara dados para salvar na view
            self.instance.auxiliar = cleaned_data.get('auxiliar_selecao')
            self.instance.auxiliares_extras_ids = cleaned_data.get('auxiliares_extras_list', '')
        else:
            self.instance.auxiliar = None
            self.instance.auxiliares_extras_ids = ''

        return cleaned_data