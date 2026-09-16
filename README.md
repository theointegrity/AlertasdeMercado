# Alertas de Mercado — Integrity Wealth Management

Sistema automatizado que monitora indicadores financeiros (dólar, títulos
do Tesouro, e futuramente outros) e envia um e-mail para a equipe quando
um gatilho configurado é atingido.

---

## 1. Uso do dia a dia (sem precisar programar)

### Alterar um gatilho
Abra `config/indicadores.yaml`, encontre o indicador e mude o número em
`gatilho`. Exemplo — mudar o dólar de R$ 5,10 para R$ 5,00:

```yaml
- id: dolar
  gatilho: 5.00   # era 5.10
```

Salve o arquivo e envie a alteração para o GitHub (`git commit` + `git push`,
ou direto pela interface web do GitHub, editando o arquivo e clicando em
"Commit changes"). Na próxima execução agendada, o novo gatilho já vale.

### Ativar/desativar um indicador
No mesmo arquivo, mude `ativo: true` para `ativo: false` (ou vice-versa).

### Adicionar/remover destinatários
Edite `config/destinatarios.yaml`. Para remover alguém sem apagar a linha,
coloque `#` na frente do e-mail.

### Consultar os últimos alertas
- Pela aba **Actions** do repositório no GitHub: cada execução aparece como
  uma linha, com um log anexado ("log-execucao-...") que pode ser baixado.
- O arquivo `logs/estado.json` (dentro do repositório) sempre mostra a
  última vez que cada indicador cruzou o gatilho.

### Saber se o sistema está funcionando
Na aba **Actions** do GitHub, execuções recentes com um ✔️ verde indicam
que rodou sem erro (mesmo que nenhum alerta tenha sido disparado — "sem
alerta" é diferente de "com erro"). Um ❌ vermelho indica falha — abra a
execução para ver o log.

---

## 2. Adicionar um indicador novo (com apoio de alguém técnico)

1. Se for um título do Tesouro novo: basta copiar um bloco em
   `config/indicadores.yaml` e ajustar `tipo`/`ano_venc`/`gatilho`. Não
   precisa mexer em código.
2. Se for um indicador de fonte totalmente nova (ex.: Ibovespa, CDI): criar
   um arquivo em `conectores/`, registrar em `CONECTORES` dentro de
   `nucleo/motor.py`, e então configurar em `config/indicadores.yaml`.

---

## 3. Implantação inicial (feita uma única vez)

1. **Criar o repositório no GitHub** (privado) e subir esta pasta inteira.

2. **Criar uma conta de e-mail dedicada** (recomendado) ou usar uma
   existente, com **senha de app** do Gmail (não a senha normal da conta):
   Conta Google → Segurança → Verificação em duas etapas → Senhas de app.

3. **Configurar os Secrets do repositório**
   (GitHub → Settings → Secrets and variables → Actions → New repository
   secret):
   - `EMAIL_USER` — endereço que envia os alertas
   - `EMAIL_PASS` — a senha de app gerada no passo 2
   - `EMAIL_NOME_EXIBICAO` — nome exibido no remetente (opcional)

4. **Conferir o agendamento** em `.github/workflows/monitor.yml` (já vem
   configurado para dias úteis, ~9h–18h de Brasília, a cada 15 min).

5. **Testar manualmente**: aba Actions → "Monitor de mercado" →
   "Run workflow". Verifique o log gerado.

6. Pronto — a partir daqui roda sozinho, sem depender de nenhum computador
   ligado.

---

## 4. Estrutura do projeto

```
config/           gatilhos e destinatários (editáveis sem programar)
conectores/       um módulo por fonte de dado (dólar, tesouro, ...)
nucleo/           lógica principal: estado/anti-spam, e-mail, motor
logs/             log de execução + estado do anti-spam (persistido no git)
.github/workflows/  agendamento automático (GitHub Actions)
main.py           ponto de entrada
```

---

## 5. Rodar localmente (para testes)

```bash
pip install -r requirements.txt
cp .env.example .env   # preencha com credenciais reais
export $(cat .env | xargs)   # carrega as variáveis no terminal (Linux/Mac)
python main.py
```
