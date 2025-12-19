from django import forms
from django.core.exceptions import ValidationError
from django.utils.safestring import mark_safe
from django.contrib.auth.models import User
from .models import Apontamento, Colaborador, Veiculo, Projeto, Setor, CodigoCliente, CentroCusto

class ApontamentoForm(forms.ModelForm):
    """
    Formulário principal para registro de apontamentos de produtividade.
    
    Funcionalidades:
    - Gerencia lógica condicional para Veículos (Frota vs Manual).
    - Gerencia Auxiliares (Principal + Extras via JS).
    - Adapta campos com base no Local de Trabalho (Obra vs Centro de Custo).
    - Implementa controle de acesso (RBAC) bloqueando campos para usuários Operacionais.
    - Validação rigorosa de sobreposição de horários (Overlap Check).
    """

    # ==========================================================================
    # CAMPOS VISUAIS E COMPLEMENTARES
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

    # --- Gestão de Veículos ---
    registrar_veiculo = forms.BooleanField(
        required=False, 
        label="Adicionar veículo"
    )
    
    veiculo_selecao = forms.ChoiceField(
        required=False, 
        label="Selecione o Veículo",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
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

    # --- Gestão de Auxiliares ---
    registrar_auxiliar = forms.BooleanField(
        required=False, 
        label="Adicionar Auxiliares?"
    )
    
    auxiliar_selecao = forms.ModelChoiceField(
        queryset=Colaborador.objects.filter(
            cargo__in=['AUXILIAR TECNICO', 'OFICIAL DE SISTEMAS']
        ), 
        required=False, 
        label="Auxiliar Principal"
    )
    
    auxiliares_extras_list = forms.CharField(
        required=False, 
        widget=forms.HiddenInput()
    )

    # ==========================================================================
    # CONFIGURAÇÕES DE META (MODELO)
    # ==========================================================================

    class Meta:
        model = Apontamento
        fields = [
            'colaborador', 'data_apontamento', 'local_execucao',
            'projeto', 'codigo_cliente', 'local_inicio_jornada', 'local_inicio_jornada_outros',
            'centro_custo', 'hora_inicio', 'hora_termino', 'ocorrencias',
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
            'centro_custo': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'centro_custo': 'Setor / Justificativa (Custo)'
        }

    # ==========================================================================
    # INICIALIZAÇÃO E CONTROLE DE ACESSO (RBAC)
    # ==========================================================================

    def __init__(self, *args, **kwargs):
        """Aplica filtros de segurança e preenchimentos automáticos baseados no perfil do usuário."""
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Filtros de Ativos
        self.fields['projeto'].queryset = Projeto.objects.filter(ativo=True)
        self.fields['centro_custo'].queryset = CentroCusto.objects.filter(ativo=True)
        self.fields['codigo_cliente'].queryset = CodigoCliente.objects.filter(ativo=True)
        
        # População do Campo Híbrido de Veículos
        veiculos_db = Veiculo.objects.all()
        choices = [('', '-- Escolha o Veículo --')]
        choices += [(v.id, str(v)) for v in veiculos_db]
        choices.append(('OUTRO', 'OUTRO (Cadastrar Novo)'))
        self.fields['veiculo_selecao'].choices = choices

        # Ajuste visual do Início de Jornada
        choices_tang = list(self.fields['local_inicio_jornada'].choices)
        self.fields['local_inicio_jornada'].choices = [c for c in choices_tang if c[0] != '']

        # Lógica de Permissões por Grupo
        if self.user:
            is_owner = self.user.is_superuser
            is_gestor = self.user.groups.filter(name='GESTOR').exists()
            is_admin = self.user.groups.filter(name='ADMINISTRATIVO').exists()
            
            if is_owner:
                self.fields['colaborador'].queryset = Colaborador.objects.all()
            elif is_admin:
                try:
                    colaborador_logado = Colaborador.objects.get(user_account=self.user)
                    setores_permitidos = colaborador_logado.setores_gerenciados.all()
                    if setores_permitidos.exists():
                        qs = Colaborador.objects.filter(setor__in=setores_permitidos)
                        qs = qs | Colaborador.objects.filter(pk=colaborador_logado.pk)
                        self.fields['colaborador'].queryset = qs.distinct()
                    else:
                        self.fields['colaborador'].queryset = Colaborador.objects.filter(pk=colaborador_logado.pk)
                    self.initial['cargo_colaborador'] = colaborador_logado.cargo
                except Colaborador.DoesNotExist:
                    self.fields['colaborador'].queryset = Colaborador.objects.none()
            elif is_gestor:
                try:
                    colaborador_logado = Colaborador.objects.get(user_account=self.user)
                    self.initial['colaborador'] = colaborador_logado
                    self.initial['cargo_colaborador'] = colaborador_logado.cargo
                    self._lock_colaborador_field(colaborador_logado)
                except Colaborador.DoesNotExist:
                    self.fields['colaborador'].queryset = Colaborador.objects.none()
            else: 
                try:
                    colaborador_logado = Colaborador.objects.get(user_account=self.user)
                    self.initial['colaborador'] = colaborador_logado
                    self.initial['cargo_colaborador'] = colaborador_logado.cargo
                    self._lock_colaborador_field(colaborador_logado)
                except Colaborador.DoesNotExist:
                    self.fields['colaborador'].queryset = Colaborador.objects.none()

        # Obrigatoriedade de Campos Core
        self.fields['colaborador'].required = True
        self.fields['hora_inicio'].required = True
        self.fields['hora_termino'].required = True

        # Injeção Automática de Classes CSS
        for name, field in self.fields.items():
            if name not in ['registrar_veiculo', 'registrar_auxiliar', 'local_inicio_jornada']:
                if 'class' not in field.widget.attrs:
                    field.widget.attrs.update({'class': 'form-control'})
                elif 'form-control' not in field.widget.attrs['class']:
                     field.widget.attrs['class'] += ' form-control'
    
    def _lock_colaborador_field(self, colaborador_logado):
        """Trava visualmente o campo do colaborador para evitar alterações não autorizadas."""
        self.fields['colaborador'].widget.attrs.update({
            'class': 'form-control pointer-events-none bg-slate-700 text-gray-400 cursor-not-allowed',
            'tabindex': '-1'
        })
        self.fields['colaborador'].queryset = Colaborador.objects.filter(pk=colaborador_logado.pk)
        self.fields['colaborador'].empty_label = None

    # ==========================================================================
    # VALIDAÇÕES CRUZADAS (CLEAN)
    # ==========================================================================

    def clean(self):
        """Validação centralizada de regras de negócio, conflitos de horário e integridade de dados."""
        cleaned_data = super().clean()
        
        colaborador = cleaned_data.get('colaborador')
        data_apontamento = cleaned_data.get('data_apontamento')
        inicio = cleaned_data.get('hora_inicio')
        termino = cleaned_data.get('hora_termino')

        # --- 1. Validação de Intervalo de Horário ---
        if inicio and termino and termino <= inicio:
            self.add_error('hora_termino', "Hora de término deve ser maior que a inicial.")

        # --- 2. Validação de Sobreposição (Overlap) ---
        if colaborador and data_apontamento and inicio and termino and inicio < termino:
            query = Apontamento.objects.filter(
                colaborador=colaborador,
                data_apontamento=data_apontamento,
                hora_inicio__lt=termino, 
                hora_termino__gt=inicio 
            )
            if self.instance and self.instance.pk:
                query = query.exclude(pk=self.instance.pk)

            if query.exists():
                conflito = query.first()
                if conflito.local_execucao == 'INT':
                    referencia = f"{str(conflito.projeto)}" if conflito.projeto else f"{str(conflito.codigo_cliente)}"
                else: 
                    referencia = f"{str(conflito.centro_custo)}" if conflito.centro_custo else "Local Externo"
                    
                inicio_str = conflito.hora_inicio.strftime('%H:%M')
                termino_str = conflito.hora_termino.strftime('%H:%M')
                data_fmt = conflito.data_apontamento.strftime('%d/%m/%Y')
                
                # Ícones para feedback visual no erro
                icon_user = '<svg class="w-4 h-4 text-gray-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" /></svg>'
                icon_place = '<svg class="w-4 h-4 text-gray-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" /></svg>'
                icon_date = '<svg class="w-4 h-4 text-gray-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>'
                icon_clock = '<svg class="w-4 h-4 text-gray-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>'

                error_message = mark_safe(f"""
                    <div class="text-left">
                        <p class="font-bold text-base text-red-300 mb-2">Conflito de horário detectado!</p>
                        <div class="bg-slate-800/80 p-3 rounded border border-red-500/30 text-sm space-y-2 mb-3 shadow-inner">
                            <div class="flex items-start gap-3">
                                <div class="mt-0.5">{icon_user}</div>
                                <span class="font-bold text-white tracking-wide">{colaborador.nome_completo.upper()}</span>
                            </div>
                            <div class="flex items-start gap-3">
                                <div class="mt-0.5">{icon_place}</div>
                                <span class="text-gray-300">{referencia}</span>
                            </div>
                            <div class="flex items-start gap-3">
                                <div class="mt-0.5">{icon_date}</div>
                                <span class="text-gray-300">{data_fmt}</span>
                            </div>
                            <div class="flex items-center gap-3">
                                <div>{icon_clock}</div>
                                <span class="font-mono text-white font-bold bg-red-900/40 px-2 rounded border border-red-900/50">{inicio_str} - {termino_str}</span>
                            </div>
                        </div>
                        <p class="text-xs text-red-300 italic">Ajuste os horários. Não é permitido inserir uma atividade dentro da outra.</p>
                    </div>
                """)
                raise ValidationError(error_message)

        # --- 3. Validação de Local e Alocação Cruzada ---
        local = cleaned_data.get('local_execucao')
        projeto = cleaned_data.get('projeto')
        cod_cliente = cleaned_data.get('codigo_cliente')
        centro_custo = cleaned_data.get('centro_custo')
        tangerino = cleaned_data.get('local_inicio_jornada')
        tangerino_obs = cleaned_data.get('local_inicio_jornada_outros')

        if local == 'INT':
            if projeto and cod_cliente:
                self.add_error('projeto', "Selecione apenas a Obra ou o Cliente, não ambos.")
                self.add_error('codigo_cliente', "Selecione apenas a Obra ou o Cliente, não ambos.")
            
            if not projeto and not cod_cliente:
                self.add_error('projeto', "Informe a Obra Específica ou o Código do Cliente.")
                self.add_error('codigo_cliente', "Informe a Obra Específica ou o Código do Cliente.")

            cleaned_data['centro_custo'] = None
            
            if tangerino == 'OUT' and not tangerino_obs:
                self.add_error('local_inicio_jornada_outros', "Especifique o local para 'Outros'.")
            
            if tangerino != 'OUT': 
                cleaned_data['local_inicio_jornada_outros'] = ""
                
        elif local == 'EXT':
            if not centro_custo:
                self.add_error('centro_custo', "Selecione o Setor / Justificativa (Custo).")
            
            if centro_custo and centro_custo.permite_alocacao:
                if projeto and cod_cliente:
                    self.add_error('projeto', "Selecione apenas a Obra ou o Cliente, não ambos.")
            else:
                cleaned_data['projeto'] = None
                cleaned_data['codigo_cliente'] = None
                self.instance.projeto = None
                self.instance.codigo_cliente = None
            
            cleaned_data['local_inicio_jornada'] = None

        # --- 4. Validação e Normalização de Veículo ---
        if cleaned_data.get('registrar_veiculo'):
            selection = cleaned_data.get('veiculo_selecao')
            if not selection:
                self.add_error('veiculo_selecao', "Selecione um veículo.")
            elif selection == 'OUTRO':
                mod = cleaned_data.get('veiculo_manual_modelo')
                pla = cleaned_data.get('veiculo_manual_placa')
                if not mod: self.add_error('veiculo_manual_modelo', "Informe o Modelo.")
                if not pla: self.add_error('veiculo_manual_placa', "Informe a Placa.")
                if pla:
                    pla = pla.upper().replace('-', '').replace(' ', '')
                    if len(pla) != 7:
                        self.add_error('veiculo_manual_placa', "A placa deve ter 7 caracteres.")
                    cleaned_data['veiculo_manual_placa'] = pla
            else:
                cleaned_data['veiculo_manual_modelo'] = None
                cleaned_data['veiculo_manual_placa'] = None
        else:
            self.instance.veiculo = None
            cleaned_data['veiculo_manual_modelo'] = None
            cleaned_data['veiculo_manual_placa'] = None

        # --- 5. Validação de Auxiliares ---
        if cleaned_data.get('registrar_auxiliar'):
            if not cleaned_data.get('auxiliar_selecao'):
                self.add_error('auxiliar_selecao', "Selecione o Auxiliar.")
            self.instance.auxiliar = cleaned_data.get('auxiliar_selecao')
            self.instance.auxiliares_extras_ids = cleaned_data.get('auxiliares_extras_list', '')
        else:
            self.instance.auxiliar = None
            self.instance.auxiliares_extras_ids = ''

        return cleaned_data