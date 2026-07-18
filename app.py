import os
import sys
import cv2
import telebot
import subprocess
import numpy as np
import logging
from flask import Flask, request

# Ваш токен от @BotFather успешно вшит!
BOT_TOKEN = "8542947216:AAETA7Zqcpx9vPw5gXo-HElfkvTpm7uMQss"
bot = telebot.TeleBot(BOT_TOKEN, threaded=False)
app = Flask(__name__)

logging.basicConfig(level=logging.INFO)

def unique_video_engine(input_video: str, output_path: str) -> bool:
    cap = cv2.VideoCapture(input_video)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    
    out_visual = f"temp_visual_{os.path.basename(output_path)}"
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(out_visual, fourcc, fps, (width, height))
    
    if not out.isOpened():
        cap.release()
        return False
        
    frame_idx = 0
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret: break
        
        # 1. Поканальный LUT-цветосдвиг пикселей кадра
        b, g, r = cv2.split(frame)
        b = cv2.add(b, 2)
        r = cv2.subtract(r, 2)
        color_shifted = cv2.merge((b, g, r))
        
        # 2. Микро-кроп и зум на 3% для сбития ИИ-ориентиров
        zoom_factor = 1.03
        nw = int(width * zoom_factor)
        nh = int(height * zoom_factor)
        resized = cv2.resize(color_shifted, (nw, nh))
        x1 = (nw - width) // 2
        y1 = (nh - height) // 2
        cropped_frame = resized[y1:y1+height, x1:x1+width]
        
        # 3. Тонкая защитная неоновая рамка
        cv2.rectangle(cropped_frame, (0, 0), (width, height), (40, 40, 40), 4)
        
        # 4. Наложение динамического цифрового шума пленки
        np.random.seed(frame_idx)
        noise = np.random.randint(-2, 3, (height, width, 3), dtype=np.int8)
        processed_frame = np.clip(cropped_frame.astype(np.int16) + noise, 0, 255).astype(np.uint8)
        
        out.write(processed_frame)
        frame_idx += 1
        
    cap.release()
    out.release()
    
    # 5. Сборка через FFmpeg (CRF=19 сохраняет идеальное HD качество) + затирание EXIF + микро-эхо
    mix_cmd = [
        'ffmpeg', '-y', '-i', out_visual, '-i', input_video,
        '-map', '0:v', '-map', '1:a', 
        '-filter_complex', '[0:v]setpts=0.99*PTS[v];[1:a]atempo=1.01,aecho=0.8:0.8:15:0.25[a]',
        '-map', '[v]', '-map', '[a]',
        '-map_metadata', '-1', '-fflags', '+bitexact', 
        '-c:v', 'libx264', '-crf', '19', '-preset', 'veryfast', '-pix_fmt', 'yuv420p', '-c:a', 'aac', output_path
    ]
    subprocess.run(mix_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    if os.path.exists(out_visual): 
        try: os.remove(out_visual)
        except Exception: pass
    return os.path.exists(output_path)

@app.route('/' + BOT_TOKEN, methods=['POST'])
def getMessage():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "!", 200

@bot.message_handler(commands=['start'])
def start_cmd(message):
    bot.reply_to(message, "👊 **Онлайн-Бот на базе Render успешно запущен 24/7!**\n\nКомпьютер можно полностью выключать. Просто отправь мне видеозапись или файл прямо с телефона!")

@bot.message_handler(content_types=['video', 'document'])
def handle_video(message):
    video_obj = message.video or (message.document if message.document and message.document.mime_type.startswith('video/') else None)
    if not video_obj: return

    status_msg = bot.reply_to(message, "⚙️ Стабильный облачный процессор Render скачивает и уникализирует тяжелое видео...")
    
    os.makedirs("downloads", exist_ok=True)
    os.makedirs("outputs", exist_ok=True)
    
    input_local_path = f"downloads/input_{video_obj.file_id[:8]}.mp4"
    output_local_path = f"outputs/unique_{video_obj.file_id[:8]}.mp4"
    
    try:
        file_info = bot.get_file(video_obj.file_id)
        file_url = f"https://telegram.org{BOT_TOKEN}/{file_info.file_path}"
        import urllib.request
        urllib.request.urlretrieve(file_url, input_local_path)
        
        success = unique_video_engine(input_local_path, output_local_path)
        
        if success:
            with open(output_local_path, 'rb') as video_file:
                bot.send_video(message.chat.id, video_file, caption="👊 Ролик успешно уникализирован в облаке 24/7! Защита от банов активна.")
            bot.delete_message(message.chat.id, status_msg.message_id)
        else:
            bot.edit_message_text("❌ Ошибка кодирования видео.", message.chat.id, status_msg.message_id)
            
    except Exception as e:
        bot.edit_message_text(f"❌ Ошибка обработки: {str(e)}", message.chat.id, status_msg.message_id)
        
    for f in [input_local_path, output_local_path]:
        if f and os.path.exists(f):
            try: os.remove(f)
            except Exception: pass

@app.route('/')
def main_index():
    render_url = os.environ.get("RENDER_EXTERNAL_URL", "https://onrender.com")
    bot.remove_webhook()
    bot.set_webhook(url=render_url + '/' + BOT_TOKEN)
    return "Bot Server is Live!", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))
