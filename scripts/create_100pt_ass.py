ass_template = """[Script Info]
Title: Short - Gingerbread Zombies 100pt
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cursive100,Pacifico,98,&H0008143C,&H000000FF,&H00B4E1FF,&H80000000,0,0,0,0,100,100,0,0,1,8.0,3.0,2,60,60,330,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.20,0:00:03.20,Cursive100,,0,0,0,,{\\fad(150,150)}Закончив оформление\\nих «костюмчиков»,
Dialogue: 0,0:00:03.20,0:00:06.40,Cursive100,,0,0,0,,{\\fad(150,150)}я взяла три листка\\nдля записей
Dialogue: 0,0:00:06.40,0:00:10.00,Cursive100,,0,0,0,,{\\fad(150,150)}и маркером написала\\nназвание на каждом.
Dialogue: 0,0:00:10.15,0:00:12.60,Cursive100,,0,0,0,,{\\fad(150,150)}«Рыжие сдобные\\nзомби».
Dialogue: 0,0:00:12.60,0:00:15.90,Cursive100,,0,0,0,,{\\fad(150,150)}Это название подходило\\nмоему состоянию зомби,
Dialogue: 0,0:00:15.90,0:00:18.30,Cursive100,,0,0,0,,{\\fad(150,150)}в котором я находилась\\nсегодня весь день,
Dialogue: 0,0:00:18.30,0:00:20.15,Cursive100,,0,0,0,,{\\fad(150,150)}в каком буду завтра,\\nкак и все последние месяцы.
Dialogue: 0,0:00:20.30,0:00:22.60,Cursive100,,0,0,0,,{\\fad(150,150)}Пять часов,\\nчетыре чашки кофе,
Dialogue: 0,0:00:22.60,0:00:25.00,Cursive100,,0,0,0,,{\\fad(150,150)}две страницы текста —\\nи завтрак готов!
Dialogue: 0,0:00:25.10,0:00:28.40,Cursive100,,0,0,0,,{\\fad(150,150)}А я готова переодеться,\\nчтобы идти в школу,
Dialogue: 0,0:00:28.40,0:00:30.80,Cursive100,,0,0,0,,{\\fad(150,150)}натянув толстовку\\nи джинсы,
Dialogue: 0,0:00:30.80,0:00:33.10,Cursive100,,0,0,0,,{\\fad(150,150)}и распустив свои\\nдлинные темные волосы.
Dialogue: 0,0:00:33.30,0:00:36.80,Cursive100,,0,0,0,,{\\fad(150,150)}Эсми уже уехала\\nна работу
Dialogue: 0,0:00:36.80,0:00:40.50,Cursive100,,0,0,0,,{\\fad(150,150)}и прихватила с собой\\n«Рыжих сдобных зомби»,
Dialogue: 0,0:00:40.50,0:00:43.50,Cursive100,,0,0,0,,{\\fad(150,150)}улыбнувшись, когда увидела\\nмое новое творение.
"""

with open("fonts/final_subtitles_100pt.ass", "w", encoding="utf-8") as f:
    f.write(ass_template)

print("Saved fonts/final_subtitles_100pt.ass successfully!")
