# Vampirinha

Jogo de ação com visão de cima para desktop (Linux), feito em Python + pygame.
Você é uma vampira numa arena enorme, cercada por hordas de inimigos com espadas e armas de fogo.
Sangue é vida **e** relógio: ele escorre sozinho, e só volta quando você machuca alguém.

## Como rodar

```bash
./run.sh
```

O script cria um ambiente virtual (`.venv`), instala o pygame e abre o jogo.
Para rodar na mão: `pip install -r requirements.txt && python3 main.py` (precisa de Python 3.9+).

## A barra de sangue

- Começa pela **metade** e **desce sozinha** com o tempo, mas **fica parada entre as ondas**
  (quando não há nenhum inimigo vivo ou por nascer).
- Tomar dano (espada: 10, tiro: 8) também faz ela descer.
- **Causar dano recupera sangue** (45% do dano causado).
- Se **enche por completo**, entra em **FRENESI**: ~35% mais rápida, ataques com +50% de dano e
  recarga 30% menor. No frenesi a barra vira um cronômetro e esvazia rápido (ainda dá para
  prolongá-lo acertando inimigos). Quando ela cai até 30, o frenesi termina.
- Se zerar fora do frenesi, ela **vira um morcego** (veja abaixo).

## Forma de morcego

Quando o sangue acaba, a vampira se transforma em morcego:

- Só tem **um ataque: morder**, no **botão direito** (bote curto para a frente, em arco). Voa seguindo o mouse.
- Voa mais rápido, mas **1 golpe e morre** (fim de jogo). Ao se transformar ela ganha só um respiro de
  0,6 s sem poder ser atingida.
- O sangue fica congelado em zero e não dá para usar elementos.
- **Matar um inimigo** devolve a forma normal, com 35% de sangue e 1 s de proteção.

## Controles

| Ação | Tecla |
| --- | --- |
| **Andar** | **ela segue o mouse**: anda até o cursor e para quando ele está em cima dela |
| Ficar parada mirando | segurar o botão esquerdo do mouse |
| Mirar | mouse |
| Elemento **braço** | `Q` |
| Elemento **perna** | `W` |
| Elemento **dente** | `E` |
| **Lançar** | **automático quando a barra de habilidades enche (3 elementos)**, na direção do ponteiro |
| Lançar antes, com 1 ou 2 elementos | `Espaço` ou botão direito do mouse |
| Cuspir de volta o tiro engolido no parry | `Espaço` ou botão direito com a fila vazia |
| Limpar a fila | `R` (ou `Backspace`) |
| **Morder** (só na forma de morcego) | botão direito do mouse |
| Pausa | `P` ou `Esc` |
| Tela cheia | `F11` |

Na vista 3/4 o cursor fica na altura do corpo: o ponto do chão para onde ela anda (e mira) fica um pouco
abaixo dele. Assim, com o cursor em cima de um inimigo o golpe vai nele, e com o cursor em cima dela ela para.

Funciona como o Magicka: você empilha até **3 elementos** na barra de cima. **Quando a barra enche, a
habilidade é lançada sozinha** (se ainda estiver em recarga, sai assim que terminar). Para lançar uma fila
incompleta (por exemplo `dente + perna`), aperte `Espaço` (ou o botão direito). O nome do que vai sair aparece embaixo da barra.

## Elementos e combos

O **primeiro** elemento define a ação; o segundo (diferente) escolhe a variação.

| Fila | Efeito |
| --- | --- |
| dente | cospe um dente em linha reta |
| braço | golpe em arco à frente |
| perna | dash na direção do mouse (invulnerável durante o dash) |
| perna + dente | dash e, ao chegar, chuva de dentes em todas as direções |
| perna + braço | dash que machuca e atordoa quem estiver à frente |
| braço + perna | **chute**: arremessa e atordoa |
| braço + dente | **soco com dente** em área |
| dente + perna | cospe a própria perna; se acertar um inimigo, a vampira **pula até ele** e causa dano em área |
| dente + braço | joga o braço como **bumerangue** (acerta na ida e na volta) |
| dente, dente, dente | **parry**: se houver tiro vindo na sua direção, ela **come o tiro** (e recupera sangue). Com a fila vazia, aperte `Espaço` (ou o botão direito) para **cuspir o tiro de volta**. Sem tiro por perto, vira um dentão perfurante |

Regras de fila:

- **Repetir fortalece**: cada elemento repetido sobe o poder (nível II e III) com mais dano, área,
  perfuração ou quantidade. Ex.: `braço, braço, braço` é um golpe muito mais forte.
- **Misturar faz as duas coisas**: com 3 elementos diferentes (ex.: `perna, dente, braço`) sai o combo
  dos dois primeiros e, logo depois, a ação do terceiro.

## Inimigos

Eles agem em grupo: um coordenador distribui papéis a cada 0,25 s e todos mantêm distância uns dos outros.

- **Espadachim**: só alguns atacam por vez (2 a 4, conforme a onda). Um ou dois vão pela frente, **dois
  flanqueiam** (contornam você em arco e atacam pelas costas, em relação a onde você está mirando) e o resto
  **ronda em anel** esperando uma vaga. Todo golpe tem um aviso curto (dá tempo de desviar ou dar dash).
- **Atirador**: mantém distância, **abre fogo cruzado** posicionando-se pelos lados e por trás, recua se você
  chega perto, **não atira com um aliado na linha de tiro** (troca de posição) e **escalona os tiros** em vez de
  disparar todos juntos. Mira com um laser vermelho e leva em conta o seu movimento. O tiro pode ser comido no parry.
- **Cachorro** (a partir da onda 2): rápido e frágil. Circula pela retaguarda, **agacha com um aviso** e dá um
  **bote em linha reta** (9 de dano). A trajetória é travada no início do bote, então um dash de lado desvia.
  No máximo 2 cachorros dão o bote ao mesmo tempo.
- As ondas crescem a cada rodada, com mais inimigos de cada tipo.

## Chefe: o Gigante

A cada **5 ondas** (5, 10, 15...) o Gigante entra primeiro, acompanhado de alguns inimigos. Ele é enorme, quase
não sofre empurrão, não é atordoado e rende menos sangue por dano (60%) que os inimigos normais. A vida dele
aparece numa barra grande embaixo da tela, e abaixo dela fica a **barra de habilidade**.

Todo golpe dele tem um **aviso vermelho no chão** e uma animação de soco própria:

| Golpe | O que faz | Dano |
| --- | --- | --- |
| **Direto** | soco reto e rápido, em linha | 14 |
| **Gancho** | soco em arco largo (200°) à frente | 16 |
| **Soco no chão** | levanta os dois punhos e bate; área grande ao redor dele | 20 |
| **Investida** | avança em linha reta com os punhos à frente | 18 |
| **Chuva de Socos** (habilidade) | marca 12 pontos no chão, os primeiros em cima de você, e os punhos caem um a um | 16 cada |

- A **barra de habilidade** enche com o tempo (~22 s) e também cada vez que ele apanha. Quando **enche, ele solta a
  Chuva de Socos** e a barra zera.
- Abaixo de 50% de vida ele **enfurece**: anda mais rápido, golpeia com menos aviso e enche a barra mais depressa.
- Para treinar contra ele: `./run.sh --wave 5` começa direto na onda 5.

## Arte

Toda a arte é vetorial e gerada por código (`tools/`), em estilo anime/chibi, e fica pronta em `assets/`
(folhas PNG + `assets/sprites.json`). O jogo só carrega os PNGs.

- **A Vampirinha**: cabelo prateado em maria-chiquinha com presilhas de morcego, olhos vermelhos com pupila de
  fenda, presinha, vestido gótico vermelho e capa de gola alta. Vista 3/4 de frente e de costas (espelhada para a
  esquerda), com animações de parada, corrida, soco, chute, cuspe, arremesso, dash, voadora, dor, mordida do parry
  e pulinho num pé só. Enquanto o braço está voando como bumerangue ela aparece **sem o braço**, e enquanto a perna
  está voando ela **pula numa perna só**. No dash ela deixa um rastro.
- **Forma de morcego**: morceguinho branco com asas vermelhas, que voa, morde e cai.
- **Rosto no HUD**: o retrato muda conforme o estado: **normal**, **frenesi** (olhos vermelhos brilhando, sorriso
  de presas), **quase sem sangue** (pálida, cansada, gota de suor), **dor** quando apanha, **morcego** e **morta**
  (olho em X, alminha saindo). Ela pisca de vez em quando. Quando ela **cospe**, o retrato faz biquinho e **os dentes
  saem voando da boca** (ou a perna, ou o tiro devolvido), quicam e somem.
- **Inimigos**: caçador de chapéu com espada, atirador com mosquete e laser de mira, cachorro de caça e o Gigante
  carrasco de capuz com manoplas de ferro (braços montados em tempo real para os socos). Todos com animações de
  andar, aviso de golpe, ataque, dor e corpo caído.
- **Efeitos de golpe**: garras vermelhas, arco dourado do chute, explosão do soco com dentes voando, corte azul
  da espada, mandíbulas do parry e da mordida, faíscas de acerto (douradas no frenesi), ondas de choque e
  rachaduras no chão nos socos do Gigante.
- **Cenário**: chão de lajotas, túmulos, cruzes, velas acesas, ossos e matinhos.

Para regerar a arte depois de mexer em `tools/art/`:

```bash
pip install -r tools/requirements.txt
python3 tools/make_assets.py
```

## Estrutura

```
main.py              o jogo (entidades, chefe, combos, HUD)
sprites.py           carrega a arte de assets/ e ajuda a desenhar (espelhar, piscar, girar efeitos)
assets/              folhas de sprites geradas (PNG) + sprites.json
tools/make_assets.py gera tudo em assets/ a partir de tools/art/ (vampira, retratos, inimigos, efeitos...)
tests/test_smoke.py  testes sem janela das mecânicas e da arte (python tests/test_smoke.py)
run.sh               atalho que cria o venv e roda
```

Os números de balanceamento (dano, dreno de sangue, frenesi etc.) ficam como constantes no topo de `main.py`.
