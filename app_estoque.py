import streamlit as st
import pandas as pd
from datetime import datetime
# Importante: service_account_from_dict é necessário para ler a chave do st.secrets
from gspread import service_account, service_account_from_dict 

# --- Configurações Iniciais ---
# Este arquivo 'credentials.json' não será mais usado, pois a chave está no Streamlit Secrets
CREDENTIALS_PATH = "credentials.json"
PLANILHA_NOME = "Estoque_Loja_Analitico"

# Colunas que serão exibidas na tabela final, NA ORDEM desejada
COLUNAS_EXIBICAO = [
    'Codigo', 
    'Produto', 
    'Grupo_de_Estoque', 
    'Em_Estoque', 
    'Media de venda semanal', 
    'Analise de estoque'
]

# Colunas que precisam de limpeza e conversão numérica
COLUNAS_NUMERICAS_LIMPEZA = ['Em_Estoque', 'Media de venda semanal'] 

# --- Formatar data (Padrão Brasileiro) ---
def formatar_br_data(d):
    """
    Formata um objeto datetime/Timestamp para o formato brasileiro dd/mm/aaaa.
    Lida com valores nulos (NaT) e vazios (pd.isna).
    """
    if pd.isna(d) or pd.isnull(d):
        return ''



    try:
        # Usa strftime, o método padrão para formatar objetos datetime
        return d.strftime("%d/%m/%Y")
    except AttributeError:
        # Retorna o valor original (string, número) se a conversão falhou
        return str(d)

# --- Configurações de Página ---
st.set_page_config(
    page_title="Consulta de Estoque Loja",
    page_icon="📦",
    layout="wide"
)

# --- Funções de Formatação (Padrão Brasileiro) ---

def formatar_br_numero(x):
    """Formata número usando ponto como separador de milhar e vírgula como decimal."""
    if pd.isna(x):
        return ''

    # 1. Decide se formata como inteiro ou com 4 casas decimais
    s = f"{x:,.4f}" if x % 1 != 0 or x == 0 else f"{int(x):,}"

    # 2. CORREÇÃO FORÇADA: Se a string formatada for pequena (ex: '758') E for composta
    # apenas por dígitos, assume que o zero e o ponto foram perdidos na leitura.
    if len(s) == 3 and s.isdigit():
        s = "0." + s # Ex: '758' vira '0.758'
    if len(s) == 2 and s.isdigit():
        s = "0.0" + s
    # 3. Inverte os separadores: vírgula milhar -> ponto, ponto decimal -> vírgula
    return s.replace('.', '#TEMP#').replace(',', '.').replace('#TEMP#', ',').strip()


# --- Conexão e Carregamento de Dados (SOLUÇÃO FINAL DE BASE64 E CONEXÃO) ---
@st.cache_data(ttl=600)
def load_data():
    """Conecta e carrega os dados da planilha, garantindo tipos numéricos."""
    try:
        if "gcp_service_account" in st.secrets:
            # --- Rotina de Limpeza e Padding da Chave Privada ---
            
            # 1. Converte para dicionário (resolve erro .copy())
            secrets_dict = dict(st.secrets["gcp_service_account"])
            private_key_corrompida = secrets_dict["private_key"]
            
            # 2. Limpa todos os caracteres indesejados (espaços, newlines, headers)
            private_key_limpa = private_key_corrompida.replace('\n', '').replace(' ', '')
            private_key_limpa = private_key_limpa.replace('-----BEGINPRIVATEKEY-----', '').replace('-----ENDPRIVATEKEY-----', '')
            
            # 3. **CORREÇÃO FINAL DO BASE64 (Padding Forçado)**
            # Corrige o erro 'Incorrect padding' e o erro '1 more than a multiple of 4'
            # Isso garante que a string Base64 tenha o tamanho correto para decodificação.
            padding_necessario = len(private_key_limpa) % 4
            if padding_necessario != 0:
                private_key_limpa += '=' * (4 - padding_necessario)
            
            # 4. Adiciona os marcadores BEGIN/END de volta com a formatação correta
            secrets_dict["private_key"] = f"-----BEGIN PRIVATE KEY-----\n{private_key_limpa}\n-----END PRIVATE KEY-----\n"
            
            # Tenta autenticar com a chave limpa e reformatada
            gc = service_account_from_dict(secrets_dict)
            
        else:
            # Se não estiver na nuvem (rodando localmente), usa o arquivo .json
            gc = service_account(filename=CREDENTIALS_PATH)
            
        planilha = gc.open(PLANILHA_NOME)
        data_atualizacao_raw = planilha.get_lastUpdateTime()
        aba = planilha.sheet1

        data = aba.get_all_records()
        df = pd.DataFrame(data)
        
        # --- Limpeza de Tipos Numéricos ---
        #for col in COLUNAS_NUMERICAS_LIMPEZA:
            #if col in df.columns:
                #df[col] = df[col].astype(str).str.strip()
                #df[col] = df[col].str.replace('R$', '', regex=False).str.strip()
                #df[col] = df[col].str.replace(',', '.', regex=False)
                #df[col] = pd.to_numeric(df[col], errors='coerce') 
                
        #df.dropna(how='all', inplace=True) 
        
        return df, data_atualizacao_raw
    except Exception as e:
        st.error(f"Erro ao carregar dados da planilha: {e}")
        return pd.DataFrame(), None

# --- Carregar e Exibir os Dados ---
df_estoque, data_atualizacao_raw = load_data()

# --- FORMATAÇÃO E EXIBIÇÃO DA DATA DE ATUALIZAÇÃO ---
data_atualizacao_formatada = ""
if data_atualizacao_raw:
    try:
        # Converte a string ISO (gspread) para datetime
        data_dt = datetime.fromisoformat(data_atualizacao_raw.replace('Z', '+00:00'))
        data_atualizacao_formatada = formatar_br_data(data_dt)
    except Exception:
        data_atualizacao_formatada = "Erro ao formatar data"


st.title("📦 Consulta de Estoque Loja")
if data_atualizacao_formatada:
    st.markdown(f"**Última Atualização:** {data_atualizacao_formatada}")
st.markdown("---")

if not df_estoque.empty:
    
    # --- PREPARO DOS DADOS DE FILTRO ---
    for col_filtro in ['Produto', 'Analise de estoque', 'Grupo_de_Estoque']:
        if col_filtro in df_estoque.columns:
            df_estoque[col_filtro] = df_estoque[col_filtro].astype(str).fillna('Não Informado')
            
    opcoes_produto = ['Todos'] + sorted(df_estoque['Produto'].unique().tolist())
    opcoes_situacao = ['Todos'] + sorted(df_estoque['Analise de estoque'].unique().tolist())
    opcoes_grupo = ['Todos'] + sorted(df_estoque['Grupo_de_Estoque'].unique().tolist())
    
    # --- INTERFACE DE FILTRO ---
    st.subheader("Filtros de Consulta")
    
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        codigo_produto = st.text_input("🔍 Filtrar por Código do Produto:", help="Filtro parcial (contém)")

    with col2:
        # COMBOBOX para Situação
        produto_filtro = st.selectbox("🏭 Filtrar por Produto:", opcoes_produto)

    with col3:
        # COMBOBOX para Situação
        situacao_filtro = st.selectbox("📝 Filtrar por Situação de Analise:", opcoes_situacao)

    with col4:
        # COMBOBOX para Grupo
        grupo_filtro = st.selectbox("🗃️ Filtrar por Grupo de Estoque:", opcoes_grupo)
        

    # --- LÓGICA DE FILTRAGEM ---
    df_filtrado = df_estoque.copy()

    # 1. Filtro por Código (text input)
    codigo_produto = codigo_produto.lower().strip()
    if codigo_produto:
        df_filtrado = df_filtrado[
            df_filtrado['Codigo']
            .astype(str)
            .str.lower()
            .str.contains(codigo_produto, na=False)
        ]

    # 2. Filtro por Situação (selectbox)
    if produto_filtro != 'Todos':
        df_filtrado = df_filtrado[df_filtrado['Produto'] == produto_filtro]
        
    if situacao_filtro != 'Todos':
        df_filtrado = df_filtrado[df_filtrado['Analise de estoque'] == situacao_filtro]
    
    # 3. Filtro por Grupo (selectbox)
    if grupo_filtro != 'Todos':
        df_filtrado = df_filtrado[df_filtrado['Grupo_de_Estoque'] == grupo_filtro]


    # --- APLICAÇÃO DA FORMATAÇÃO E SELEÇÃO DE COLUNAS ---
    
    # 1. Seleciona e copia APENAS as colunas desejadas
    try:
        df_display = df_filtrado[COLUNAS_EXIBICAO].copy()
    except KeyError as e:
        st.error(f"Erro: A coluna {e} não foi encontrada na sua planilha. Por favor, verifique os nomes exatos das colunas: {COLUNAS_EXIBICAO}")
        st.stop() 

    # 2. Aplica as formatações nas colunas específicas
    for col in COLUNAS_NUMERICAS_LIMPEZA:
        if col in df_display.columns:
            df_display[col] = df_display[col].apply(formatar_br_numero)
        
    # --- EXIBIÇÃO ---
    st.markdown("---")
    st.subheader(f"Resultados Encontrados ({len(df_filtrado)} itens)")

    if not df_filtrado.empty:
        # Exibe o DataFrame formatado (agora como strings BR)
        st.dataframe(
            df_display, 
            use_container_width=True
        )
    else:
        st.warning("Nenhum resultado encontrado para os filtros aplicados.")

else:
    st.error("Não foi possível carregar os dados. Verifique suas credenciais, o nome da planilha ou a conexão.")



















