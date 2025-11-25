from django import forms
from django.core.exceptions import ValidationError
from .models import Apontamento, Colaborador, Veiculo, Projeto, Setor

class ApontamentoForm(forms.ModelForm):
    """
    Formulário principal para registro de apontamentos de produtividade.
    Gerencia lógica condicional para Veículos (Frota vs Manual), 
    Auxiliares (Principal + Extras) e Local de Trabalho (Obra vs Setor).
    """

    # ==========================================================================
    # CAMPOS VISUAIS E READ-ONLY
    # ==========================================================================
    nome_projeto = forms.CharField(
        required=False, 
        disabled=True, 
        label="Nome da Obra", 
        initial="Aguardando seleção..."
    )
    cargo_colaborador = forms.CharField(
        required=False, 
        disabled=True, 
        label="Cargo", 
        initial="-"
    )

    # ==========================================================================
    # GESTÃO DE VEÍCULOS
    # Permite selecionar da frota ou cadastrar manualmente ('OUTRO')
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
    # Permite selecionar Auxiliar Principal e lista oculta de Extras
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
            'projeto', 'local_inicio_jornada', 'local_inicio_jornada_outros',
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
        super().__init__(*args, **kwargs)
        
        # Filtros para garantir que apenas ativos apareçam
        self.fields['projeto'].queryset = Projeto.objects.filter(ativo=True)
        self.fields['setor'].queryset = Setor.objects.filter(ativo=True)
        
        # --- Popula Campo de Veículo (Híbrido) ---
        veiculos_db = Veiculo.objects.all()
        choices = [('', '-- Escolha o Veículo --')]
        choices += [(v.id, str(v)) for v in veiculos_db]
        choices.append(('OUTRO', 'OUTRO (Cadastrar Novo)'))
        self.fields['veiculo_selecao'].choices = choices

        # --- Limpeza de Opções do Tangerino ---
        # Remove a opção vazia "---------" gerada por padrão
        choices_tang = list(self.fields['local_inicio_jornada'].choices)
        self.fields['local_inicio_jornada'].choices = [c for c in choices_tang if c[0] != '']

        # Define obrigatoriedade de campos base
        self.fields['colaborador'].required = True
        self.fields['hora_inicio'].required = True
        self.fields['hora_termino'].required = True

        # Aplica classe CSS padrão em todos os campos (exceto checkboxes/radios)
        for name, field in self.fields.items():
            if name not in ['registrar_veiculo', 'registrar_auxiliar', 'local_inicio_jornada']:
                field.widget.attrs.update({'class': 'form-control'})

    def clean(self):
        """
        Validação cruzada de campos dependentes (Local, Veículo, Horários).
        """
        cleaned_data = super().clean()
        
        # --- 1. Validação de Local (Obra vs Setor) ---
        local = cleaned_data.get('local_execucao')
        projeto = cleaned_data.get('projeto')
        setor = cleaned_data.get('setor')
        tangerino = cleaned_data.get('local_inicio_jornada')
        tangerino_obs = cleaned_data.get('local_inicio_jornada_outros')

        if local == 'INT': # Dentro da Obra
            if not projeto:
                self.add_error('projeto', "Selecione o Código da Obra.")
            cleaned_data['setor'] = None
            
            # Validação Tangerino
            if tangerino == 'OUT' and not tangerino_obs:
                self.add_error('local_inicio_jornada_outros', "Especifique o local para 'Outros'.")
            
            # Limpa obs se não for 'Outros'
            if tangerino != 'OUT': 
                cleaned_data['local_inicio_jornada_outros'] = ""
                
        elif local == 'EXT': # Fora da Obra
            if not setor:
                self.add_error('setor', "Selecione o Setor.")
            # Limpa campos de obra
            cleaned_data['projeto'] = None
            cleaned_data['local_inicio_jornada'] = None
            self.instance.projeto = None

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