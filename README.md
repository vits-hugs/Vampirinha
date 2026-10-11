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

- Começa pela **metade** e **desce sozinha** com o tempo.
- Tomar dano (espada: 10, tiro: 8) também faz ela descer.
- **Causar dano recupera sangue** (45% do dano causado).
- Se **enche por completo**, entra em **FRENESI**: ~35% mais rápida, ataques com +50% de dano e
  recarga 30% menor. No frenesi a barra vira um cronômetro e esvazia rápido (ainda dá para
  prolongá-lo acertando inimigos). Quando ela cai até 30, o frenesi termina.
- Se zerar fora do frenesi, acabou.

## Controles

| Ação | Tecla |
| --- | --- |
| Andar | `W` `A` `S` `D` |
| Mirar | mouse |
| Elemento **perna** | `Shift` |
| Elemento **braço** | botão direito do mouse |
| Elemento **dente** | `Espaço` |
| **Lançar** o que está na fila | botão esquerdo do mouse (na direção do ponteiro) |
| Limpar a fila | `Q` |
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

- **Espadachim**: corre até você e golpeia depois de um breve aviso (dá tempo de desviar ou dar dash).
- **Atirador**: mantém distância, mira com um laser vermelho e atira. O tiro dele pode ser comido no parry.
- As ondas crescem a cada rodada, com mais espadachins e atiradores.

## Estrutura

```
main.py              o jogo inteiro (entidades, combos, HUD)
tests/test_smoke.py  testes sem janela das mecânicas (python tests/test_smoke.py)
run.sh               atalho que cria o venv e roda
```

Os números de balanceamento (dano, dreno de sangue, frenesi etc.) ficam como constantes no topo de `main.py`.
