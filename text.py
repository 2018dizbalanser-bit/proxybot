from aiogram.utils.markdown import pre



def hours(h1: int = 6, m1: int = 15, h2: int = 3, m2: int = 56):
    day_hour = 24
    hour_minutes = 60
    day_minutes = 60*24

    if h1 > 24 or h2 > 24:
        print("В одном дне не может быть больше 24 часов")
    if m1 > 60 or m2 > 60:
        print("В одном часу не может быть больше 60 минут")

    # переводим все в минуты
    h1_m1 = h1*hour_minutes+m1
    h2_m2 = h2*hour_minutes+m2
    range_minutes = h2_m2 - h1_m1 # разница в минутах

    count_minutes = m1
    for i in range(0, range_minutes+1):

        print(f"{h1}:{count_minutes}")

        h1 = h1
        if count_minutes >= 59:
            h1 += 1

        count_minutes += 1
        if count_minutes >= hour_minutes:
            count_minutes = 0


hours(38, 67, 1, 5)