from django import forms
from django.core.exceptions import ValidationError
from django.utils.safestring import mark_safe
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import datetime, timedelta
from .models import Apontamento, Colaborador, Veiculo, Projeto, Setor, CodigoCliente, CentroCusto

class ApontamentoForm(forms.ModelForm):
    """
    Formulário principal para registro de apontamentos de produtividade.
    Gerencia a entrada de dados, validações de regra de negócio (conflitos, locais)
    e controle de acesso aos campos baseados no nível do usuário (RBAC).
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
    
    # Campo oculto para armazenar IDs de múltiplos auxiliares (manipulado via JS)
    auxiliares_extras_list = forms.CharField(
        required=False, 
        widget=forms.HiddenInput()
    )

    # --- Adicionais de Folha ---
    em_plantao = forms.BooleanField(
        required=False,
        label="Atividade em Plantão?"
    )
    data_plantao = forms.DateField(
        required=False,
        widget=forms.HiddenInput(),
        input_formats=['%d/%m/%Y', '%Y-%m-%d']
    )
    dorme_fora = forms.BooleanField(
        required=False,
        label="Dorme Fora Nesta Data?"
    )
    data_dorme_fora = forms.DateField(
        required=False,
        widget=forms.HiddenInput(),
        input_formats=['%d/%m/%Y', '%Y-%m-%d']
    )

    # ==========================================================================
    # CONFIGURAÇÕES DE META (MODELO)
    # ==========================================================================

    class Meta:
        model = Apontamento
        fields = [
            'colaborador', 'data_apontamento', 'local_execucao',
            'projeto', 'codigo_cliente',
            'centro_custo', 'hora_inicio', 'hora_termino', 'ocorrencias',
            'veiculo_manual_modelo', 'veiculo_manual_placa',
            'em_plantao', 'data_plantao', 'dorme_fora', 'data_dorme_fora'
        ]
        widgets = {
            'data_apontamento': forms.TextInput(attrs={
                'class': 'form-control cursor-pointer bg-slate-800 text-left font-bold text-emerald-400 border-emerald-500/50 pl-3',
                'readonly': 'readonly', 
                'placeholder': 'DD/MM/AAAA'
            }),
            'hora_inicio': forms.TimeInput(attrs={'type': 'time'}),
            'hora_termino': forms.TimeInput(attrs={'type': 'time'}),
            'ocorrencias': forms.Textarea(attrs={'rows': 3}),
            'local_execucao': forms.Select(attrs={'class': 'form-select'}),
            'centro_custo': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'centro_custo': 'Setor / Justificativa (Custo)'
        }

    # ==========================================================================
    # INICIALIZAÇÃO E CONTROLE DE ACESSO (RBAC)
    # ==========================================================================

    def __init__(self, *args, **kwargs):
        """
        Inicializa o formulário aplicando filtros de permissão baseados no usuário logado.
        Define quais colaboradores podem ser selecionados e popula selects dinâmicos.
        """
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Configurações iniciais de Querysets e Formatos
        self.fields['data_apontamento'].input_formats = ['%d/%m/%Y', '%Y-%m-%d']
        self.fields['projeto'].queryset = Projeto.objects.filter(ativo=True)
        self.fields['centro_custo'].queryset = CentroCusto.objects.filter(ativo=True)
        self.fields['codigo_cliente'].queryset = CodigoCliente.objects.filter(ativo=True)
        
        # Popula combobox de veículos (Banco de Dados + Opção Manual)
        veiculos_db = Veiculo.objects.all()
        choices = [('', '-- Escolha o Veículo --')]
        choices += [(v.id, str(v)) for v in veiculos_db]
        choices.append(('OUTRO', 'OUTRO (Cadastrar Novo)'))
        self.fields['veiculo_selecao'].choices = choices

        # Lógica de Permissão (RBAC)
        if self.user:
            is_owner = self.user.is_superuser
            is_gestor = self.user.groups.filter(name='GESTOR').exists()
            is_admin = self.user.groups.filter(name='ADMINISTRATIVO').exists()
            
            if is_owner:
                # Superusuário vê tudo
                self.fields['colaborador'].queryset = Colaborador.objects.all()
            
            elif is_admin:
                # Admin vê seu próprio perfil e os setores que gerencia
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
                # Gestor vê apenas a si mesmo (mas o campo fica travado visualmente)
                try:
                    colaborador_logado = Colaborador.objects.get(user_account=self.user)
                    self.initial['colaborador'] = colaborador_logado
                    self.initial['cargo_colaborador'] = colaborador_logado.cargo
                    self._lock_colaborador_field(colaborador_logado)
                except Colaborador.DoesNotExist:
                    self.fields['colaborador'].queryset = Colaborador.objects.none()
            
            else: 
                # Usuário padrão vê apenas a si mesmo (travado)
                try:
                    colaborador_logado = Colaborador.objects.get(user_account=self.user)
                    self.initial['colaborador'] = colaborador_logado
                    self.initial['cargo_colaborador'] = colaborador_logado.cargo
                    self._lock_colaborador_field(colaborador_logado)
                except Colaborador.DoesNotExist:
                    self.fields['colaborador'].queryset = Colaborador.objects.none()

        self.fields['colaborador'].required = True
        self.fields['hora_inicio'].required = True
        self.fields['hora_termino'].required = True

        # Aplicação massiva de classes CSS (Tailwind/Bootstrap)
        for name, field in self.fields.items():
            if name not in ['registrar_veiculo', 'registrar_auxiliar', 'em_plantao', 'dorme_fora']:
                if 'class' not in field.widget.attrs:
                    field.widget.attrs.update({'class': 'form-control'})
                elif 'form-control' not in field.widget.attrs['class']:
                     field.widget.attrs['class'] += ' form-control'
    
    def _lock_colaborador_field(self, colaborador_logado):
        """Bloqueia visualmente o campo colaborador para usuários sem permissão de troca."""
        self.fields['colaborador'].widget.attrs.update({
            'class': 'form-control pointer-events-none bg-slate-700 text-gray-400 cursor-not-allowed',
            'tabindex': '-1'
        })
        self.fields['colaborador'].queryset = Colaborador.objects.filter(pk=colaborador_logado.pk)
        self.fields['colaborador'].empty_label = None

    def clean(self):
        """
        Validação centralizada de regras de negócio.
        - Bloqueia datas/horários futuros.
        - Detecta conflitos de agenda (overlap).
        - Valida obrigatoriedade condicional de campos.
        """
        cleaned_data = super().clean()
        
        colaborador = cleaned_data.get('colaborador')
        data_apontamento = cleaned_data.get('data_apontamento')
        inicio = cleaned_data.get('hora_inicio')
        termino = cleaned_data.get('hora_termino')

        # 1. Bloqueio de Datas Futuras
        if data_apontamento and inicio and termino:
            # Pega o "Agora" com fuso horário correto
            agora = timezone.localtime(timezone.now())
            
            # Monta a data/hora completa do Início
            dt_inicio = timezone.make_aware(
                datetime.combine(data_apontamento, inicio)
            )
            
            # Monta a data/hora completa do Término
            dt_termino = timezone.make_aware(
                datetime.combine(data_apontamento, termino)
            )

            # LÓGICA DA VIRADA: Se terminou "antes" de começar (ex: 23h as 02h), 
            # significa que o término é no dia seguinte.
            if dt_termino < dt_inicio:
                dt_termino += timedelta(days=1)

            # Verifica se é futuro
            if dt_inicio > agora:
                self.add_error('hora_inicio', "O horário de início não pode ser no futuro.")
            
            if dt_termino > agora:
                self.add_error('hora_termino', "O horário de término não pode ser no futuro.")

        # Se houver erros, retorna imediatamente
        if self.errors:
            return cleaned_data

        # 2. Detecção de Conflitos (Overlap)
        if colaborador and data_apontamento and inicio and termino and inicio < termino:
            query = Apontamento.objects.filter(
                colaborador=colaborador,
                data_apontamento=data_apontamento,
                hora_inicio__lt=termino, 
                hora_termino__gt=inicio 
            )
            # Exclui o próprio registro se for edição
            if self.instance and self.instance.pk:
                query = query.exclude(pk=self.instance.pk)

            if query.exists():
                conflito = query.first()
                
                # Montagem dos dados para a mensagem de erro
                if conflito.local_execucao == 'INT':
                    referencia = f"{str(conflito.projeto)}" if conflito.projeto else f"{str(conflito.codigo_cliente)}"
                else: 
                    referencia = f"{str(conflito.centro_custo)}" if conflito.centro_custo else "Local Externo"
                    
                inicio_str = conflito.hora_inicio.strftime('%H:%M')
                termino_str = conflito.hora_termino.strftime('%H:%M')
                data_fmt = conflito.data_apontamento.strftime('%d/%m/%Y')
                
                # Ícones SVG inline para o alerta
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

        # 3. Validação de Local e Contexto
        local = cleaned_data.get('local_execucao')
        projeto = cleaned_data.get('projeto')
        cod_cliente = cleaned_data.get('codigo_cliente')
        centro_custo = cleaned_data.get('centro_custo')

        if local == 'INT':
            # Regras para trabalho interno (Obra/Cliente)
            if projeto and cod_cliente:
                self.add_error('projeto', "Selecione apenas a Obra ou o Cliente, não ambos.")
                self.add_error('codigo_cliente', "Selecione apenas a Obra ou o Cliente, não ambos.")
            
            if not projeto and not cod_cliente:
                self.add_error('projeto', "Informe a Obra Específica ou o Código do Cliente.")
                self.add_error('codigo_cliente', "Informe a Obra Específica ou o Código do Cliente.")

            cleaned_data['centro_custo'] = None
                
        elif local == 'EXT':
            # Regras para trabalho externo (Centro de Custo/Justificativa)
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
            
        # 4. Validação de Veículos
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

        # 5. Validação de Auxiliares
        if cleaned_data.get('registrar_auxiliar'):
            if not cleaned_data.get('auxiliar_selecao'):
                self.add_error('auxiliar_selecao', "Selecione o Auxiliar.")
            
            self.instance.auxiliar = cleaned_data.get('auxiliar_selecao')
            # Nota: 'auxiliares_extras_ids' é um atributo temporário para uso na View
            self.instance.auxiliares_extras_ids = cleaned_data.get('auxiliares_extras_list', '')
        else:
            self.instance.auxiliar = None
            self.instance.auxiliares_extras_ids = ''

        # 6. Validação de Adicionais (Plantão e Dorme-Fora)
        if cleaned_data.get('em_plantao'):
            dt_plantao = cleaned_data.get('data_plantao')
            if not dt_plantao:
                self.add_error(None, "Selecione a Data do Plantão no calendário.")
            elif dt_plantao != data_apontamento:
                # Aqui garantimos que, mesmo se o calendário falhar, o backend barra
                self.add_error(None, "A Data do Plantão deve ser a mesma do registro principal.")

        if cleaned_data.get('dorme_fora'):
            dt_dorme = cleaned_data.get('data_dorme_fora')
            if not dt_dorme:
                self.add_error(None, "Selecione a Data do Dorme-Fora no calendário.")
            elif dt_dorme != data_apontamento:
                self.add_error(None, "A Data do Dorme-Fora deve ser a mesma do registro principal.")
                
        return cleaned_data
    