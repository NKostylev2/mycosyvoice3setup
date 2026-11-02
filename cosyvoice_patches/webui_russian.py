# CosyVoice 3 Russian WebUI
import os
import sys
import glob
import argparse
import random
import gradio as gr
import numpy as np
import torch
import torchaudio

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(ROOT_DIR, "third_party", "Matcha-TTS"))

from cosyvoice.cli.cosyvoice import AutoModel
from cosyvoice.utils.file_utils import logging
from cosyvoice.utils.common import set_all_random_seed

ALLTALK_VOICES_DIR = r"E:\AI-Dubbing\alltalk_tts\voices"

MODE_CROSS = "Кросс-язычный клон (Cross-Lingual)"
MODE_ZEROSHOT = "3-сек клон (Zero-Shot с текстом)"
MODE_INSTRUCT = "Управление эмоциями и стилем (Instruct)"
MODE_PRESET = "Встроенные дикторы"

inference_mode_list = [MODE_CROSS, MODE_INSTRUCT, MODE_ZEROSHOT]

instruct_dict = {
    MODE_CROSS: "1. Выберите голос из пресетов AllTalk или загрузите свой аудиофайл (от 3 до 30 секунд).\n2. Введите текст на русском или любом другом языке.\n3. Нажмите кнопку «Сгенерировать речь».",
    MODE_INSTRUCT: "1. Выберите эталонный голос (или пресет).\n2. Выберите эмоцию (кнопками ниже или введите своё описание).\n3. Нажмите кнопку «Сгенерировать речь».",
    MODE_ZEROSHOT: "1. Выберите аудиофайл с голосом.\n2. Введите точный текст, который произносится в аудио-образце.\n3. Нажмите «Сгенерировать речь».",
    MODE_PRESET: "1. Выберите встроенного диктора из списка.\n2. Нажмите «Сгенерировать речь»."
}

EMOTION_PRESETS = {
    "😠 Злобно / С возмущением": "请非常生气地说一句话。",
    "😄 Очень радостно": "请非常开心地说一句话。",
    "😢 Грустно / Печально": "请非常伤心地说一句话。",
    "🤫 Шёпотом / Очень тихо": "Please say a sentence in a very soft voice.",
    "📢 Громко / Экспрессивно": "Please say a sentence as loudly as possible.",
    "⚡ Быстрый темп": "请用尽可能快地语速说一句话。",
    "🐢 Медленный темп": "请用尽可能慢地语速说一句话。"
}

def get_preset_voices():
    if os.path.exists(ALLTALK_VOICES_DIR):
        files = sorted(glob.glob(os.path.join(ALLTALK_VOICES_DIR, "*.wav")))
        return {os.path.basename(f): f for f in files}
    return {}

preset_voice_dict = get_preset_voices()
preset_voice_choices = ["(Загрузить свой файл)"] + list(preset_voice_dict.keys())

def generate_seed():
    return random.randint(1, 100000000)

def change_instruction(mode):
    return instruct_dict.get(mode, "")

def set_emotion(emotion_label):
    return EMOTION_PRESETS.get(emotion_label, "")

def generate_audio(tts_text, mode_radio, preset_dropdown, prompt_wav_upload, prompt_wav_record,
                   prompt_text, instruct_text, seed, speed):
    if not tts_text or not tts_text.strip():
        gr.Warning("Введите текст для синтеза!")
        return (cosyvoice.sample_rate, default_data)

    prompt_wav = None
    if prompt_wav_upload is not None:
        prompt_wav = prompt_wav_upload
    elif prompt_wav_record is not None:
        prompt_wav = prompt_wav_record
    elif preset_dropdown and preset_dropdown != "(Загрузить свой файл)":
        prompt_wav = preset_voice_dict.get(preset_dropdown)

    if not prompt_wav and mode_radio in [MODE_CROSS, MODE_INSTRUCT, MODE_ZEROSHOT]:
        gr.Warning("Пожалуйста, выберите пресет голоса или загрузите свой аудиофайл (WAV)!")
        return (cosyvoice.sample_rate, default_data)

    set_all_random_seed(seed)
    tts_text = tts_text.strip()

    if mode_radio == MODE_CROSS:
        if "<|endofprompt|>" not in tts_text:
            tts_text = f"You are a helpful assistant.<|endofprompt|>{tts_text}"
        logging.info(f"Cross-lingual synthesis: {tts_text}")
        for i in cosyvoice.inference_cross_lingual(tts_text, prompt_wav, stream=False, speed=speed):
            yield (cosyvoice.sample_rate, i['tts_speech'].numpy().flatten())

    elif mode_radio == MODE_INSTRUCT:
        inst = instruct_text.strip() if instruct_text else "Please say a sentence with expression."
        if "<|endofprompt|>" not in inst:
            inst = f"You are a helpful assistant. {inst}<|endofprompt|>"
        logging.info(f"Instruct synthesis: {tts_text} | Instruct: {inst}")
        if hasattr(cosyvoice, "inference_instruct2"):
            for i in cosyvoice.inference_instruct2(tts_text, inst, prompt_wav, stream=False, speed=speed):
                yield (cosyvoice.sample_rate, i['tts_speech'].numpy().flatten())
        else:
            for i in cosyvoice.inference_instruct(tts_text, sft_spk[0], inst, stream=False, speed=speed):
                yield (cosyvoice.sample_rate, i['tts_speech'].numpy().flatten())

    elif mode_radio == MODE_ZEROSHOT:
        p_text = prompt_text.strip() if prompt_text else ""
        if hasattr(cosyvoice, "inference_instruct2") and "<|endofprompt|>" not in p_text:
            p_text = f"You are a helpful assistant.<|endofprompt|>{p_text}"
        logging.info(f"Zero-shot synthesis: {tts_text}")
        for i in cosyvoice.inference_zero_shot(tts_text, p_text, prompt_wav, stream=False, speed=speed):
            yield (cosyvoice.sample_rate, i['tts_speech'].numpy().flatten())

    else:
        for i in cosyvoice.inference_sft(tts_text, sft_spk[0], stream=False, speed=speed):
            yield (cosyvoice.sample_rate, i['tts_speech'].numpy().flatten())

def main():
    custom_css = """
    .emotion-btn { margin: 2px !important; }
    """
    with gr.Blocks(title="CosyVoice 3 WebUI (Русский интерфейс)", css=custom_css) as demo:
        gr.Markdown("# 🎙️ FunAudioLLM CosyVoice 3 (0.5B-2512) — WebUI")
        gr.Markdown("Zero-shot клонирование голоса, поддержка русского языка, перенос тембра и управление эмоциями.")

        with gr.Row():
            with gr.Column(scale=2):
                tts_text = gr.Textbox(
                    label="Текст для озвучки (Русский или любой язык)",
                    lines=3,
                    value="Три миллиона? Мошенник! Твой магазин - сплошное надувательство!"
                )

                with gr.Row():
                    mode_radio = gr.Radio(
                        choices=inference_mode_list,
                        label="Режим работы",
                        value=MODE_CROSS
                    )
                    speed = gr.Slider(
                        label="Скорость речи",
                        minimum=0.5,
                        maximum=2.0,
                        value=1.0,
                        step=0.1
                    )

                instruction_box = gr.Textbox(
                    label="Памятка по режиму",
                    value=instruct_dict[MODE_CROSS],
                    interactive=False,
                    lines=2
                )

                gr.Markdown("### 🎤 Эталонный голос для клонирования:")
                preset_dropdown = gr.Dropdown(
                    label="Пресеты голосов из AllTalk (voices)",
                    choices=preset_voice_choices,
                    value="male_01.wav" if "male_01.wav" in preset_voice_choices else preset_voice_choices[0]
                )

                with gr.Row():
                    prompt_wav_upload = gr.Audio(sources=["upload"], type="filepath", label="Или загрузите свой аудиофайл (WAV, 3-30 сек)")
                    prompt_wav_record = gr.Audio(sources=["microphone"], type="filepath", label="Или запишите с микрофона")

                prompt_text = gr.Textbox(
                    label="Текст аудио-образца (нужен только в режиме '3-сек клон')",
                    placeholder="Введите текст, который звучит в эталонном аудио...",
                    lines=1,
                    visible=True
                )

                gr.Markdown("### 🎭 Управление эмоциями (для режима Instruct):")
                with gr.Row():
                    btn_angry = gr.Button("😠 Злость / Возмущение", size="sm")
                    btn_happy = gr.Button("😄 Радость", size="sm")
                    btn_sad = gr.Button("😢 Грусть", size="sm")
                    btn_whisper = gr.Button("🤫 Шёпот", size="sm")
                    btn_loud = gr.Button("📢 Громко", size="sm")
                    btn_fast = gr.Button("⚡ Быстро", size="sm")

                instruct_text = gr.Textbox(
                    label="Инструкция эмоции / стиля (Instruct)",
                    placeholder="Например: 请非常生气地说一句话。 или выберите кнопку выше",
                    lines=1
                )

                with gr.Row():
                    seed_button = gr.Button("🎲 Случайный Seed", scale=1)
                    seed = gr.Number(value=42, label="Seed генерации", precision=0, scale=2)

                generate_btn = gr.Button("Сгенерировать речь 🔊", variant="primary", size="lg")

            with gr.Column(scale=1):
                audio_output = gr.Audio(label="Результат синтеза", autoplay=True)

        mode_radio.change(fn=change_instruction, inputs=[mode_radio], outputs=[instruction_box])
        seed_button.click(fn=generate_seed, outputs=[seed])

        btn_angry.click(fn=lambda: set_emotion("😠 Злобно / С возмущением"), outputs=[instruct_text])
        btn_happy.click(fn=lambda: set_emotion("😄 Очень радостно"), outputs=[instruct_text])
        btn_sad.click(fn=lambda: set_emotion("😢 Грустно / Печально"), outputs=[instruct_text])
        btn_whisper.click(fn=lambda: set_emotion("🤫 Шёпотом / Очень тихо"), outputs=[instruct_text])
        btn_loud.click(fn=lambda: set_emotion("📢 Громко / Экспрессивно"), outputs=[instruct_text])
        btn_fast.click(fn=lambda: set_emotion("⚡ Быстрый темп"), outputs=[instruct_text])

        generate_btn.click(
            fn=generate_audio,
            inputs=[tts_text, mode_radio, preset_dropdown, prompt_wav_upload, prompt_wav_record,
                    prompt_text, instruct_text, seed, speed],
            outputs=[audio_output]
        )

    demo.launch(server_name="0.0.0.0", server_port=args.port)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=50000)
    parser.add_argument("--model_dir", type=str, default="pretrained_models/Fun-CosyVoice3-0.5B")
    args = parser.parse_args()

    cosyvoice = AutoModel(model_dir=args.model_dir)
    sft_spk = cosyvoice.list_available_spks()
    if len(sft_spk) == 0:
        sft_spk = [""]
    default_data = np.zeros(cosyvoice.sample_rate)
    main()
