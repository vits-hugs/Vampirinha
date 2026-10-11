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

- Só tem **um ataque: morder**, no **botão direito** (bote curto para a frente, em arco).
- Voa mais rápido, mas **1 golpe e morre** (fim de jogo). Ao se transformar ela ganha só um respiro de
  0,6 s sem poder ser atingida.
- O sangue fica congelado em zero e não dá para usar elementos.
- **Matar um inimigo** devolve a forma normal, com 35% de sangue e 1 s de proteção.

## Controles

| Ação | Tecla |
| --- | --- |
| Andar | `W` `A` `S` `D` |
| Mirar | mouse |
| Elemento **perna** | `Shift` |
| Elemento **braço** | botão esquerdo do mouse |
| Elemento **dente** | `Espaço` |
| **Lançar** o que está na fila | botão direito do mouse (na direção do ponteiro) |
| Limpar a fila | `Q` |
| **Morder** (só na forma de morcego) | botão direito do mouse |
| Pausa | `P` ou `Esc` |
| Tela cheia | `F11` |

Funciona como o Magicka: você empilha até **3 elementos** na barra de cima e depois lança.
O nome do que vai sair aparece embaixo da barra.

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
| dente, dente, dente | **parry**: se houver tiro vindo na sua direção, ela **come o tiro** (e recupera sangue). Com a fila vazia, clique para **cuspir o tiro de volta**. Sem tiro por perto, vira um dentão perfurante |

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

## Estrutura

```
main.py              o jogo inteiro (entidades, combos, HUD)
tests/test_smoke.py  testes sem janela das mecânicas (python tests/test_smoke.py)
run.sh               atalho que cria o venv e roda
```

Os números de balanceamento (dano, dreno de sangue, frenesi etc.) ficam como constantes no topo de `main.py`.
