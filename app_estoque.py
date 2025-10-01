import streamlit as st
import pandas as pd
# Importante: service_account_from_dict é necessário para ler a chave do st.secrets
from gspread import service_account, service_account_from_dict 

# --- Configurações Iniciais ---
CREDENTIALS_PATH = "credentials.json"
PLANILHA_NOME = "Estoque_Loja_Analitico"

# Colunas que serão exibidas na tabela final, NA ORDEM desejada
COLUNAS_EXIBICAO = [
    'Codigo', 
    'Produto', 
    'Grupo_de_Estoque', 
    'Em_Estoque', 
    ' Media de venda semanal', 
    'Analise de estoque'
]

# Colunas que precisam de limpeza e conversão numérica
COLUNAS_NUMERICAS_LIMPEZA = ['Em_Estoque', ' Media de venda semanal'] 

# --- Configurações de Página ---
st.set_page_config(
    page_title="Consulta de Estoque",
    page_icon="📦",
    layout="wide"
)

# --- Funções de Formatação (Padrão Brasileiro) ---

def formatar_br_numero(x):
    """Formata número usando ponto como separador de milhar e vírgula como decimal."""
    if pd.isna(x):
        return ''
    
    # Decide se formata como inteiro ou com duas casas decimais
    s = f"{x:,.2f}" if x % 1 != 0 or x == 0 else f"{int(x):,}" 
    
    # Inverte os separadores: vírgula milhar -> ponto, ponto decimal -> vírgula
    return s.replace('.', '#TEMP#').replace(',', '.').replace('#TEMP#', ',')


# --- Conexão e Carregamento de Dados (AJUSTADO PARA A NUVEM) ---
@st.cache_data(ttl=600)
def load_data():
    """Conecta e carrega os dados da planilha, garantindo tipos numéricos."""
    try:
        # Tenta carregar do Streamlit Secrets (modo Cloud)
        if "gcp_service_account" in st.secrets:
            # Carrega as credenciais a partir do dicionário de segredos injetado
            gc = service_account_from_dict(st.secrets["gcp_service_account"])
        else:
            # Se não estiver na nuvem (rodando localmente), usa o arquivo .json
            gc = service_account(filename=CREDENTIALS_PATH)
            
        planilha = gc.open(PLANILHA_NOME)
        aba = planilha.sheet1

        data = aba.get_all_records()
        df = pd.DataFrame(data)
        
        # --- LIMPEZA: GARANTE QUE OS DADOS SÃO NUMÉRICOS NO PYTHON ---
        for col in COLUNAS_NUMERICAS_LIMPEZA:
            if col in df.columns:
                # 1. Converte para string (para limpar)
                df[col] = df[col].astype(str).str.strip()
                # 2. Remove possíveis símbolos de moeda (R$) e espaços
                df[col] = df[col].str.replace('R$', '', regex=False).str.strip()
                # 3. Se a planilha usa VÍRGULA como decimal, trocamos para PONTO (padrão Pandas)
                df[col] = df[col].str.replace(',', '.', regex=False)
                # 4. Força a conversão para float (número decimal)
                df[col] = pd.to_numeric(df[col], errors='coerce') 
                
        df.dropna(how='all', inplace=True) 

        return df
    except Exception as e:
        st.error(f"Erro ao carregar dados da planilha: {e}")
        return pd.DataFrame()

# --- Carregar e Exibir os Dados ---
df_estoque = load_data()

st.title("📦 Consulta de Estoque")
st.markdown("---")

if not df_estoque.empty:
    
    # --- PREPARO DOS DADOS DE FILTRO ---
    # Garante que as colunas de filtro existem e que os valores 'NaN' são tratados para o combobox
    for col_filtro in ['Analise de estoque', 'Grupo_de_Estoque']:
        if col_filtro in df_estoque.columns:
            df_estoque[col_filtro] = df_estoque[col_filtro].astype(str).fillna('Não Informado')

    # Opções para os combobox
    opcoes_situacao = ['Todos'] + sorted(df_estoque['Analise de estoque'].unique().tolist())
    opcoes_grupo = ['Todos'] + sorted(df_estoque['Grupo_de_Estoque'].unique().tolist())
    
    # --- INTERFACE DE FILTRO ---
    st.subheader("Filtros de Consulta")
    
    col1, col2, col3 = st.columns(3)

    with col1:
        codigo_produto = st.text_input("🔍 Filtrar por Código do Produto:", help="Filtro parcial (contém)")

    with col2:
        # COMBOBOX para Situação
        situacao_filtro = st.selectbox("📝 Filtrar por Situação de Analise:", opcoes_situacao)

    with col3:
        # COMBOBOX para Grupo
        grupo_filtro = st.selectbox("🏭 Filtrar por Grupo de Estoque:", opcoes_grupo)
        

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

