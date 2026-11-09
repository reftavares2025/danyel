# Danyel 🏠⚡

**Agente de IA que encontra pessoas querendo comprar imóvel nas redes sociais, dá uma nota para cada uma e entrega os melhores contatos no WhatsApp de quem vende.**

Criado por **Régis Automações**. Feito em Python e roda no seu próprio computador. A IA usa a sua assinatura do Claude (via Claude Code), então **não tem custo de API**.

---

## O problema que ele resolve

Todo dia tem gente postando em grupo de Facebook coisas como *"procuro casa em Cosmópolis, pago à vista"* ou perguntando *"qual o valor?"* no post de uma imobiliária. Esses são compradores prontos, mas os posts somem no meio do feed e ninguém tem tempo de procurar em dezenas de grupos, cidades e redes todos os dias.

O Danyel faz essa busca, separa quem realmente pode comprar de quem só está curioso, quer alugar ou é outro corretor anunciando, e entrega a lista pronta.

## O que ele entrega

| Entrega | Como chega |
|---|---|
| **Relatório diário de compradores** com nome, link direto do post, o que a pessoa escreveu, telefone (se tiver) e **nota de 0 a 100** | Mensagem no WhatsApp do vendedor ou aprovador, 2× ao dia |
| **Motivo da nota**: intenção (comprar, trocar, investir, alugar), forma de pagamento, urgência | Junto com cada lead no relatório |
| **Mensagem de abordagem personalizada**, que cita o que a pessoa postou | No painel e no relatório, pronta para copiar |
| **Comentário automático** nos posts de quem procura imóvel, com o WhatsApp do vendedor | No Facebook, com limite diário |
| **Funil de vendas**: Novo → Qualificado → Abordado → Respondeu → Visita → Proposta → Fechado | Painel web local (`http://localhost:5556`) |
| **Lembrete de retorno** para quem foi abordado e não respondeu em X dias | No painel |
| **Campanha de anúncios no Meta** (Facebook + Instagram) com raio geográfico, criativos e link direto para o WhatsApp | Scripts em `meta_daniel/` |

## Como funciona

```
 ┌───────────────┐   ┌──────────────┐   ┌───────────────┐   ┌──────────────────┐
 │ 1. CAÇA       │ → │ 2. FILTRO    │ → │ 3. CÉREBRO IA │ → │ 4. ENTREGA       │
 │ Facebook      │   │ regras rápidas│  │ nota 0-100    │   │ WhatsApp do      │
 │ Google        │   │ (aluguel,    │   │ intenção      │   │ aprovador        │
 │ Meta (páginas │   │  corretor,   │   │ pagamento     │   │ + comentário no  │
 │  e Instagram) │   │  repetido)   │   │ mensagem      │   │   post           │
 └───────────────┘   └──────────────┘   └───────────────┘   └──────────────────┘
```

1. **Caça** (`coletor_facebook.py`, `coletor_google.py`, `coletor_meta.py`)
   - Faz buscas no Facebook com frases como "procuro casa", "compro casa" e "aceita troca", girando entre as cidades da região. Muda as combinações todo dia.
   - Pesquisa no Google posts de compra no Facebook, Instagram, OLX e sites de imóveis. O Google devolve o link direto do post, que o Facebook esconde na busca dele.
   - Lê, pela API oficial do Meta, as mensagens recebidas nas páginas e os comentários no Instagram e nos anúncios.
   - Tudo isso é **só leitura**, feito em ritmo humano (pausas aleatórias e poucas buscas por ciclo).
2. **Filtro** (`sinais.py`): regras sem IA que detectam telefone, rede social e sinais de compra, e descartam aluguel, vendedor e corretor.
3. **Cérebro** (`cerebro.py`): o Claude analisa cada post e devolve nota, intenção, forma de pagamento, urgência e uma mensagem de abordagem. Só passa quem tem nota mínima (padrão 50) e um perfil compatível com a oferta. Por exemplo, se o vendedor não aceita financiamento, quem só pode comprar financiado fica de fora.
4. **Entrega** (`robo.py`, `whatsapp.py`, `comentador.py`, `messenger.py`): manda o relatório pelo WhatsApp Web e comenta nos posts. Se estiver no modo `robo_envia`, envia as mensagens que o aprovador liberar respondendo `APROVO 1 3`, `APROVO TODOS` ou `NÃO 2`.

## Travas de segurança

Automação em rede social derruba perfil se for agressiva. Por isso o Danyel tem limites fixos:

- **No máximo 10 mensagens por dia**, sendo até 5 pelo Messenger.
- **No máximo 8 comentários por dia**, nunca dois no mesmo post, sempre com pausa entre eles.
- **Só envia entre 8h e 20h.**
- **Nada vai para desconhecido sem aprovação** quando está no modo `robo_envia`.
- **LGPD:** o botão "pediu para não ser contatado" apaga os dados e bloqueia a pessoa para sempre. Páginas com dados sensíveis (de saúde, por exemplo) são ignoradas.
- **IA isolada:** o Claude roda sem ferramentas, sem MCP e numa pasta temporária vazia. Texto de post é tratado como dado, nunca como instrução, então um post com "ignore as instruções" não consegue fazer nada.
- **Painel local:** ele só escuta em `127.0.0.1` e recusa requisições de outros sites.
- **Dados locais:** tudo fica em `data/danyel.db`, só no seu computador.

## Dois jeitos de usar

### Modo painel (manual)
Dê dois cliques em **`INICIAR DANYEL.bat`**. O painel abre em `http://localhost:5556`.

1. Em **Caçar hoje**, arraste o botão **⚡ Danyel** para a barra de favoritos do Chrome.
2. Abra as buscas do dia, selecione o texto do post de quem quer comprar e clique em ⚡ Danyel.
3. No **Funil**, abra o lead, revise a mensagem, envie e marque como **Abordado**.

### Modo robô (automático)
1. Rode **`ABRIR FACEBOOK DO DANIEL.bat`**. Ele abre um Chrome separado, na porta 9223. Faça login com o Facebook do vendedor uma única vez.
2. Deixe o seu Chrome com o WhatsApp Web logado.
3. Rode **`ATIVAR AGENDAMENTO.ps1`**. O Agendador do Windows passa a:
   - varrer as redes **todo dia às 9h e às 15h** e mandar o relatório;
   - ler as aprovações e enviar **a cada 30 minutos, das 8h às 20h**.
4. Para desligar, rode `DESATIVAR AGENDAMENTO.ps1`.

## Comandos

```bash
python -m danyel                      # painel web
python -m danyel analisar "texto"     # testa a IA com um post
python -m danyel rota                 # mostra as buscas de hoje
python -m danyel simular              # varre e mostra o relatório SEM enviar nada
python -m danyel ciclo                # varre, analisa e manda o relatório
python -m danyel aprovacoes           # lê o APROVO e envia o que foi liberado
python -m pytest -q tests             # testes
```

## Instalação

**Requisitos:** Windows, Python 3.11+, Google Chrome, [Claude Code](https://claude.com/claude-code) logado com sua assinatura e [browser-harness](https://github.com/browser-use/browser-harness) para controlar o Chrome.

```bash
git clone https://github.com/<seu-usuario>/danyel.git
cd danyel
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

Ou é só dar dois cliques em `INICIAR DANYEL.bat`, que prepara tudo na primeira vez.

## Configuração (`danyel.yaml`)

Tudo que muda de um cliente para outro fica em um único arquivo:

- **`vendedor`**: nome, WhatsApp e tom de voz.
- **`ofertas`**: o que está à venda, com preço, condições, comprador ideal e quem desqualifica. Pode ter mais de uma oferta.
- **`caca`**: cidades, frases de busca e hashtags.
- **`robo`**: modo (`contato_direto` ou `robo_envia`), notas mínimas, limites diários e horário.
- **`cerebro`**: liga ou desliga a IA e escolhe o modelo.

Seus dados pessoais (telefones reais e caminho do token do Meta) vão em **`danyel.local.yaml`**. Esse arquivo vale por cima do `danyel.yaml` e **nunca vai para o git**. Os números que aparecem neste repositório são fictícios.

> O exemplo que vem configurado é a venda de um imóvel em Cosmópolis/SP. Para vender outra coisa, como carros, terrenos ou serviços, basta trocar as ofertas e as frases de busca.

## Estrutura

```
danyel/
├── __main__.py          comandos de terminal
├── web.py + templates/  painel (Flask)
├── caca.py              rota de buscas do dia
├── coletor_facebook.py  varredura do Facebook (só leitura)
├── coletor_google.py    varredura pelo Google
├── coletor_meta.py      mensagens e comentários via API oficial do Meta
├── sinais.py            filtro por regras (sem IA)
├── cerebro.py           análise com Claude (isolado)
├── robo.py              ciclo automático + aprovações + travas
├── comentador.py        comentários nos posts
├── whatsapp.py          envio e leitura pelo WhatsApp Web
├── messenger.py         envio pelo Messenger
├── navegador.py         ponte com o Chrome (browser-harness)
└── db.py                SQLite: leads, histórico, não-contatar
meta_daniel/             scripts que sobem criativos e criam a campanha no Meta Ads
tests/                   testes automatizados
```

## Aviso

Automatizar ações em redes sociais pode ir contra os termos de uso das plataformas. As travas reduzem o risco, mas não eliminam. Use com moderação, respeite a LGPD e quem pediu para não ser contatado.

---

Feito por **Régis Automações** 🤖
