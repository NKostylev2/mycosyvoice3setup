# Generate full ASS subtitles file for Short_Рыжие_Сдобные_Зомби.mp4

ass_text = """[Script Info]
Title: Short - Gingerbread Zombies
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: CursiveBanner,Pacifico,68,&H0008143C,&H000000FF,&H00B4E1FF,&H70000000,0,0,0,0,100,100,0,0,1,5.5,3.0,2,80,80,320,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.20,0:00:03.20,CursiveBanner,,0,0,0,,{\\fad(150,150)}Закончив оформление их «костюмчиков»,
Dialogue: 0,0:00:03.20,0:00:06.40,CursiveBanner,,0,0,0,,{\\fad(150,150)}я взяла три листка для записей
Dialogue: 0,0:00:06.40,0:00:10.00,CursiveBanner,,0,0,0,,{\\fad(150,150)}и маркером написала название печенья на каждом.
Dialogue: 0,0:00:10.20,0:00:12.60,CursiveBanner,,0,0,0,,{\\fad(150,150)}«Рыжие сдобные зомби».
Dialogue: 0,0:00:12.60,0:00:15.90,CursiveBanner,,0,0,0,,{\\fad(150,150)}Это название очень подходило моему состоянию зомби,
Dialogue: 0,0:00:15.90,0:00:18.30,CursiveBanner,,0,0,0,,{\\fad(150,150)}в котором я находилась сегодня весь день,
Dialogue: 0,0:00:18.30,0:00:20.10,CursiveBanner,,0,0,0,,{\\fad(150,150)}в каком буду завтра, как и все последние месяцы.
Dialogue: 0,0:00:20.30,0:00:22.60,CursiveBanner,,0,0,0,,{\\fad(150,150)}Пять часов, четыре чашки кофе,
Dialogue: 0,0:00:22.60,0:00:24.90,CursiveBanner,,0,0,0,,{\\fad(150,150)}две страницы английского текста — и завтрак готов!
Dialogue: 0,0:00:25.10,0:00:28.40,CursiveBanner,,0,0,0,,{\\fad(150,150)}А я готова переодеться, чтобы идти в школу,
Dialogue: 0,0:00:28.40,0:00:33.10,CursiveBanner,,0,0,0,,{\\fad(150,150)}натянув толстовку, джинсы и распустив волосы.
Dialogue: 0,0:00:33.30,0:00:36.80,CursiveBanner,,0,0,0,,{\\fad(150,150)}Эсми уже уехала на работу
Dialogue: 0,0:00:36.80,0:00:40.50,CursiveBanner,,0,0,0,,{\\fad(150,150)}и прихватила с собой моих «Рыжих сдобных зомби»,
Dialogue: 0,0:00:40.50,0:00:43.50,CursiveBanner,,0,0,0,,{\\fad(150,150)}улыбнувшись, когда увидела мое новое творение.
"""

with open("fonts/short_subtitles.ass", "w", encoding="utf-8") as f:
    f.write(ass_text)

print("Saved fonts/short_subtitles.ass")
