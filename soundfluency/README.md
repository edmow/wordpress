# SoundFluency 🎙️

Pipeline de produção de vídeos para **prática de inglês** (estilo "listen and repeat"):
você escreve as frases num JSON, ele gera narração em inglês com TTS de alta qualidade,
monta os cartões visuais, as pausas para repetição e entrega o **MP4 pronto para o YouTube**
(+ legenda `.srt` sincronizada).

## Como funciona um vídeo gerado

1. **Cartão de título** com o nome da lição
2. Para cada frase:
   - áudio em **velocidade natural**
   - **pausa** para o aluno repetir
   - áudio em **velocidade lenta** (0.7x)
   - pausa novamente
   - áudio natural mais uma vez
3. Frase em inglês grande + tradução em português no cartão
4. Áudio final com loudness normalizado (padrão -16 LUFS, adequado para YouTube)

Todo o padrão acima é configurável no `config.yaml` (seção `pacing`).

## Instalação

```bash
cd soundfluency
pip install -r requirements.txt
sudo apt install ffmpeg          # ou brew install ffmpeg no macOS
python -m soundfluency doctor    # confere se está tudo ok
```

Na primeira execução o modelo Kokoro (~340 MB) é baixado automaticamente.

## Uso

```bash
# gera o vídeo de uma lição em output/
python -m soundfluency build lessons/001-daily-routines.json

# várias lições de uma vez
python -m soundfluency build lessons/*.json

# formato vertical para Shorts/Reels/TikTok
python -m soundfluency build lessons/001-daily-routines.json --vertical
```

## Criando uma lição

Crie um JSON em `lessons/`:

```json
{
  "id": "002",
  "title": "At the Restaurant",
  "subtitle": "No restaurante — frases essenciais",
  "level": "A2",
  "phrases": [
    { "en": "Could I see the menu, please?", "pt": "Poderia ver o cardápio, por favor?" },
    { "en": "I'd like a table for two.", "pt": "Eu gostaria de uma mesa para dois." }
  ]
}
```

Campos opcionais: `"background": "backgrounds/minha-imagem.jpg"` fixa uma imagem de fundo;
`"config": { ... }` sobrescreve qualquer chave do config.yaml só para essa lição.

## Qualidade do TTS (o coração do projeto)

| Engine | Qualidade | Custo | Quando usar |
|---|---|---|---|
| **kokoro** (padrão) | ★★★★★ para inglês — nº 1 do TTS Arena entre modelos abertos | Grátis, roda local (CPU serve) | Produção normal |
| **elevenlabs** | ★★★★★+ (melhor absoluta) | Pago por caractere (`ELEVENLABS_API_KEY`) | Quando quiser o máximo |
| **espeak** | ★ (robótico) | Grátis | Só para testar o pipeline |

Vozes Kokoro recomendadas (mude em `tts.voice` no config.yaml):

- `af_heart` — feminina americana, a mais natural (padrão)
- `af_bella` — feminina americana, mais expressiva
- `am_michael` — masculina americana
- `bf_emma` / `bm_george` — sotaque britânico

> Nota: o "Voicebox" da Meta nunca foi liberado ao público. O app open source
> [Voicebox](https://github.com/jamiepine/voicebox) (MIT) é ótimo como *estúdio* interativo
> e usa engines equivalentes (Kokoro, Chatterbox) — este projeto usa o mesmo Kokoro
> direto no pipeline, sem depender de interface gráfica.

## Imagens de fundo

Três modos (config `backgrounds.mode`):

- **auto** (padrão): usa imagens da pasta `backgrounds/` se houver; senão gera
  gradientes procedurais elegantes — nunca trava por falta de asset
- **images**: exige imagens na pasta
- **gradient**: sempre gradiente gerado

Imagens recebem escurecimento + desfoque automáticos para o texto ficar sempre legível.
Veja `backgrounds/README.md` para fontes gratuitas (Pexels, Unsplash, Pixabay).

## Estrutura

```
soundfluency/
├── config.yaml            # toda a configuração (vídeo, tts, pacing, estilo, fundos)
├── lessons/               # suas lições em JSON
├── backgrounds/           # suas imagens de fundo (opcional)
├── output/                # vídeos e legendas gerados (não versionado)
└── soundfluency/          # código do pipeline
    ├── tts.py             # engines: kokoro / elevenlabs / espeak
    ├── cards.py           # renderização dos cartões (Pillow)
    ├── backgrounds.py     # imagens ou gradientes procedurais
    ├── video.py           # montagem com ffmpeg + .srt
    └── cli.py             # comandos build / doctor
```

## Roadmap sugerido

- [ ] Voz pt-BR opcional falando a tradução (Chatterbox Multilingual tem modelo pt-BR dedicado)
- [ ] Destaque palavra-a-palavra (karaokê) usando timestamps do TTS
- [ ] Música de fundo suave com ducking automático
- [ ] Upload direto para o YouTube via API
