#!/bin/python3
from email import message
import json
import vk_api
import asyncio
import re
import datetime
import os
import database
import math
import requests
import random
import time
import config
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor

# раскомментить на проде
PATH = r"C:\Users\user\Desktop\mf\murteambot"


conf = config.config()
TOKEN = conf.data['vktoken']
ADVTOKEN = conf.data['advancedtoken']
ALLOWED = conf.data['vkallowed']
LOGS = conf.data['vklogs']
VK_ID = conf.data['vkid']
ALBUM = conf.data['album']

vks = vk_api.VkApi(token=TOKEN)
vks._auth_token()
vk = vks.get_api()
vks_user = vk_api.VkApi(token=ADVTOKEN)
vks_user._auth_token()
vk_adv = vks_user.get_api()
longpoll = VkBotLongPoll(vks, VK_ID)

# заранее посчитаем, сколько изображений в папке, чтобы иметь возможность загружать новые без редактирования кода

images_count = os.listdir(f"{PATH}/images")
images_count.remove("words.txt")
images_count = len(images_count)


''' Немного логов'''


def log(text, dm=1):
    vk.messages.send(peer_id=LOGS, message=text,
                     random_id=0, disable_mentions=dm)


def getTimeFromUnix(u):
    return str(datetime.datetime.fromtimestamp(u))


def getUnixTime():
    return int(time.time())


async def check_cb(event):
    vk.messages.send(
        peer_id=event.message["peer_id"], message="Пинг", random_id=0)


async def hello_cb(event):
    vk.messages.send(
        peer_id=event.message["peer_id"], message=f"Привет вездекодерам!", random_id=0)


async def image_cb(event):
    images, over_list = generate_local_image(event.message["from_id"], 5)
    if over_list:
        vk.messages.send(
            peer_id=event.message["peer_id"], message=f"Упс... Кажется, вы видели все, что мы для вас приготовили. Сейчас обнулим ваши счетчики и покажем старые картинки.", random_id=0)
    vk.messages.send(
        peer_id=event.message["peer_id"], message=f"Вот 5 случайных картинок.", random_id=0, attachment=",".join(images))


def generate_local_image(uid, num, team_id=0, return_indices=False):
    # генерирует num случайных картинок, которые не видел пользователь в случае одиночной игры (его команда имеет идентификатор 0), или которые не видели участники команды с tid = team_id (тогда uid не имеет значения)
    over_list = False
    document = database.find_document(
        database.teams_values, {"uid": uid, "tid": team_id})
    if document:
        excluded = set(document["excluded"])
    else:
        excluded = set()
    all_indices = range(1, images_count)
    all_indices = list(set(all_indices) - excluded)
    if len(all_indices) < num:
        over_list = True
        database.update_document(database.teams_values, {
                                 "uid": uid, "tid": team_id}, {"excluded": []})
        excluded = set()
    indices = set()
    while len(indices) < num:
        indices.add(random.choice(all_indices))
    images = [f"{PATH}/images/{index}.jpg" for index in indices]
    excluded, indices = list(excluded), list(indices)
    attachments = []
    for image in images:
        upload = vk_api.VkUpload(vk)
        photo = upload.photo_messages(image)
        owner_id = photo[0]['owner_id']
        photo_id = photo[0]['id']
        access_key = photo[0]['access_key']
        attachments.append(f'photo{owner_id}_{photo_id}_{access_key}')
    if document:
        excluded += indices
        database.update_document(database.teams_values, {
                                 "uid": event.message["from_id"], "tid": team_id}, {"excluded": excluded})
    else:
        excluded = indices
        database.insert_document(database.teams_values, {
                                 "uid": event.message["from_id"], "excluded": excluded, "tid": team_id})
    if return_indices:
        return attachments, indices, over_list
    return attachments, over_list


def generate_remote_image(uid, num, team_id=0):
    over_list = False
    document = database.find_document(
        database.teams_values, {"uid": uid, "tid": team_id})
    if document:
        excluded = set(document["excluded"])
    else:
        excluded = set()
    url = database.find_document(database.teams, {"admin_id": uid})[
        "source_url"]
    owner = url.split("_")[0].split("-")[1]
    album_id = url.split("_")[1]
    photos = vk_adv.photos.get(owner_id=f"-{owner}", album_id=album_id)["items"]
    images =[{
            "photo": ("photo" + str(photo["owner_id"]) + "_" +
                      str(photo["id"])), "text": photo["text"]
        } for photo in photos]
    
    for image in images:
        if not image["text"]:
            images.remove(image)
    captions = {}
    for image in images:
        captions[image["photo"]] = image["text"]
        # captions.append(
        #     {
        #         image["photo"]: image["text"]
        #     }
        # )
    images = set([("photo" + str(photo["owner_id"]) + "_" +
                      str(photo["id"])) for photo in photos])
    images -= excluded
    if len(images) < num:
        over_list = True
        database.update_document(database.teams_values, {
                                 "uid": uid, "tid": team_id}, {"excluded": []})
        excluded = set()
    usable_images = set()
    images = list(images)
    while len(usable_images) < num:
        usable_images.add(random.choice(images))
    excluded, usable_images = list(excluded), list(usable_images)
    if document:
        excluded += usable_images
        database.update_document(database.teams_values, {
                                 "uid": event.message["from_id"], "tid": team_id}, {"excluded": excluded})
    else:
        excluded = usable_images
        database.insert_document(database.teams_values, {
                                 "uid": event.message["from_id"], "excluded": excluded, "tid": team_id})
    # captions_returned = []
    
    return usable_images, captions, over_list


def upload_image(filename):
    # загружает фотографию на сервера VK и возвращает ее как объект attachment (вида photo1234_5678_vezdekod)
    upload = vk_api.VkUpload(vk)
    photo = upload.photo_messages(filename)
    owner_id = photo[0]['owner_id']
    photo_id = photo[0]['id']
    access_key = photo[0]['access_key']
    return f'photo{owner_id}_{photo_id}_{access_key}'


def create_keyboard_for_signing():
    # генерирует клавиатуру для get_sign_for_local_dataset
    keyboard = VkKeyboard(one_time=False)
    # False Если клавиатура должна оставаться откртой после нажатия на кнопку
    # True если она должна закрваться

    keyboard.add_button("Оставить без изменений",
                        color=VkKeyboardColor.SECONDARY)

    keyboard.add_line()  # Обозначает добавление новой строки
    keyboard.add_button("Закрыть редактирование",
                        color=VkKeyboardColor.NEGATIVE)

    return keyboard.get_keyboard()


def get_sign_for_local_dataset(file_id, uid, peer_id):
    # функция управляет процессом разметки, в частности генерирует сообщения для администраторов с кнопками и версией подсказки из default-источника, а также взаимодействует с БД
    image = upload_image(f"{PATH}/images/{file_id}.jpg")
    images = os.listdir(f"{PATH}/images")
    if file_id >= len(images):
        # это последняя картинка в перезаписи, удаляем завершенную сессию
        database.delete_document(database.admin_sessions, {
                                 "uid": uid, "mode": "sign_local_dataset"})
    else:
        database.update_document(database.admin_sessions, {
                                 "uid": uid, "mode": "sign_local_dataset"}, {"expected": file_id+1})
    text = f"Текущая подпись: {get_current_sign(f'{file_id}.jpg', 'default')}"
    vk.messages.send(peer_id=peer_id, attachment=image, random_id=0,
                     keyboard=create_keyboard_for_signing(), message=text)
    if file_id >= len(images):
        vk.messages.send(peer_id=peer_id, message="Ура! Полный цикл перезаписи пройден.",
                         random_id=0, keyboard=VkKeyboard.get_empty_keyboard())


async def start_sign_cb(event):
    # функция для запуска процесса ручной разметки локального датасета
    if not event.message["from_id"] in ALLOWED:
        return False
    document = database.find_document(database.admin_sessions, {
                                      "uid": event.message["from_id"], "mode": "sign_local_dataset"})
    if not document:
        # сессии перезаписи подписей еще нет, мы ее инициируем
        vk.messages.send(
            peer_id=event.message["peer_id"], message="Производится настройка подписей локального датасета. Введите свои подписи через пробел на каждую картинку, что увидите.", random_id=0)
        database.insert_document(database.admin_sessions, {
                                 "uid": event.message["from_id"], "mode": "sign_local_dataset", "expected": 1})
        get_sign_for_local_dataset(
            1, event.message["from_id"], event.message["peer_id"])
    if document:
        vk.messages.send(
            peer_id=event.message["peer_id"], message=f"Производится старая настройка (на этапе {document['expected']}), завершите ее командой \"Закрыть редактирование\".", random_id=0)


def sign_local_dataset(filename, text):
    # функция для записи новой подписи к данной картинке в датасете
    f = open(f"{PATH}/images/another_wordlist.txt", encoding="cp1251").read().split("\n")
    string_exists = False
    for index, string in enumerate(f):
        if string.startswith(filename):
            f[index] = f"{filename}\t{text}"
            string_exists = True
            break
    if not string_exists:
        f += [f"{filename}\t{text}"]
    f = "\n".join(f)
    new_f = open(f"{PATH}/images/another_wordlist.txt", 'w', encoding="cp1251")
    new_f.write(f)
    new_f.close()


def get_current_sign(filename, source="another"):
    # выводит текущую подпись картинки. Источник - default (VK-совский), another (размеченный нами), или custom - ссылка на альбом VK.
    print(filename, "get_curerent_sign")
    if source == "another":
        f = open(f"{PATH}/images/another_wordlist.txt", encoding="cp1251").read().split("\n")
    if source == "default":
        f = open(f"{PATH}/images/words.txt", encoding="cp1251").read().split("\n")
    for index, string in enumerate(f):
        if string.startswith(filename):
            return f[index].split("\t")[1]
    return False


async def sign_handler_cb(event):
    # функция обрабатывает все сообщения, если активирован режим ручной разметки локального датасета
    if not event.message["from_id"] in ALLOWED:
        return False
    document = database.find_document(database.admin_sessions, {
                                      "uid": event.message["from_id"], "mode": "sign_local_dataset"})
    if not document:
        return False
    text = event.message["text"]
    if text == "Оставить без изменений":
        message = "оставлено без изменений"
        new_text = get_current_sign(f"{document['expected']-1}.jpg", "default")
    elif text == "Закрыть редактирование":
        message = "сессия закрыта преждевременно"
        new_text = None
        database.delete_document(database.admin_sessions, {
                                 "uid": event.message["from_id"], "mode": "sign_local_dataset"})
    else:
        new_text = text
        message = f"текст изменен на \"{text}\""
    if new_text:
        sign_local_dataset(f"{document['expected']-1}.jpg", new_text)
    vk.messages.send(
        peer_id=event.message["peer_id"], message=f"Картинка {document['expected']-1}: {message}.", random_id=0, keyboard=VkKeyboard.get_empty_keyboard())
    if not new_text:
        return
    get_sign_for_local_dataset(
        document["expected"], event.message["from_id"], event.message["peer_id"])


def generate_invite_team():
    return str(time.time() % 1024).replace(".", "")[:7:-1]


def create_team(peer_id, admin_id, personal=False, team_name=False, mode="multiplayer", tid=False):
    document = database.find_document(
        database.teams, {"users": {"$all": [admin_id]}, "personal": False})
    if document:
        # администратор хочет создать команду, но он уже в ней находится. Дадим ему выбор.
        # При этом персональная команда - это не команда, из нее можно выйти без подтверждения. А чтобы выйти из многопользовательской игры в другую команту или в одиночную игру лучше переспросить.

        keyboard = VkKeyboard(one_time=True)
        keyboard.add_button("Закрыть", color=VkKeyboardColor.SECONDARY)
        keyboard.add_line()
        keyboard.add_button(
            f"Покинуть команду", color=VkKeyboardColor.NEGATIVE)

        keyboard = keyboard.get_keyboard()

        vk.messages.send(
            peer_id=peer_id, message=f"Вы уже состоите в команде \"{document['team_name']}\". Чтобы играть одному или в новом составе, сначала выйдите из предыдущей команды.", random_id=0, keyboard=keyboard)
        return
    if personal:
        if database.find_document(database.teams, {"admin_id": admin_id, "personal": True}):
            database.delete_document(
                database.teams, {"admin_id": admin_id, "personal": True})
        database.insert_document(database.teams, {"admin_id": admin_id, "users": [
            admin_id], "personal": True, "mode": "oneplayer", "team_name": "Персональная комната", "source": "default", "invite": (0 if tid else generate_invite_team()), "game_state": {"activeUser": admin_id, "active": False, "users_state": [{
                "uid": admin_id,
                "score": 0
            }]}})
    else:
        database.insert_document(database.teams, {"admin_id": admin_id, "users": [admin_id], "source": "default", "personal": False, "mode": mode, "invite": (0 if tid else generate_invite_team()), "team_name": (f"Комната #{random.randint(1, 128000)}" if not team_name else team_name), "game_state": {
            "active": False,
            "activeUser": admin_id,
            "leader": admin_id,
            "users_state": [{
                "uid": admin_id,
                "score": 0
            }]}})
    return database.find_document(database.teams, {"admin_id": admin_id})


async def create_team_cb(event):
    team_name = event.message["text"][16:] or False
    team = create_team(event.message["peer_id"],
                       event.message["from_id"], False, team_name, "unset")
    keyboard = VkKeyboard(one_time=True)
    keyboard.add_button(
        f"Мультиплеер {team['invite']}", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button(
        f"Мультиплеер c ведущим {team['invite']}", color=VkKeyboardColor.SECONDARY)
    keyboard.add_line()
    keyboard.add_button(f"Расформировать команду",
                        color=VkKeyboardColor.NEGATIVE)
    keyboard = keyboard.get_keyboard()

    vk.messages.send(
        peer_id=event.message["peer_id"], message=f"Вы успешно создали команду \"{team['team_name']}\". В нее можно приглашать людей по инвайт-коду {team['invite']}.\nТеперь выберите, во что играть.", random_id=0, keyboard=keyboard)


async def change_multiplayer_mode_cb(event):
    uid = event.message["from_id"]
    team_id, mode = [x[::-1]
                     for x in event.message["text"][::-1].split(maxsplit=1)]
    document = database.find_document(database.teams, {"invite": team_id})
    if not document:
        vk.messages.send(
            peer_id=event.message["peer_id"], message="Упс... Похоже, такой команды не существует.", random_id=0)
        return
    if document["admin_id"] != uid:
        vk.messages.send(
            peer_id=event.message["peer_id"], message="Вы не можете выполнить это действие.", random_id=0)
        return
    mode_list = {
        "мультиплеер": "multiplayer",
        "мультиплеер с ведущим": "multiplayer+"
    }
    mode = mode_list[mode.lower()]
    vk.messages.send(
        peer_id=event.message["peer_id"], message=f"В команде \"{document['team_name']}\" изменен тип игры.", random_id=0)
    database.update_document(database.teams, {"admin_id": uid}, {"mode": mode})


async def change_oneplayer_mode_cb(event):
    uid = event.message["from_id"]
    team_id, mode = [x[::-1]
                     for x in event.message["text"][::-1].split(maxsplit=1)]
    document = database.find_document(
        database.teams, {"invite": 0, "admin_id": uid})
    if not document:
        vk.messages.send(
            peer_id=event.message["peer_id"], message="Что-то пошло не так. 1", random_id=0)
        return
    if document["admin_id"] != uid:
        vk.messages.send(
            peer_id=event.message["peer_id"], message="Что-то пошло не так. 2", random_id=0)
        return
    source_list = {
        "от murteam": "another",
        "от организаторов вездекода": "default",
        "ссылка на альбом vk": "remote"

    }
    mode = source_list[mode.lower()]
    keyboard = VkKeyboard(one_time=True)
    keyboard.add_button(
        f"Начать одиночную игру", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button(
        f"Расформировать команду", color=VkKeyboardColor.NEGATIVE)
    keyboard = keyboard.get_keyboard()

    vk.messages.send(
        peer_id=event.message["peer_id"], message=f"Источник изменен.", random_id=0, keyboard=keyboard)
    database.update_document(
        database.teams, {"admin_id": uid}, {"source": mode})
    if mode == "remote":
        vk.messages.send(
            peer_id=event.message["peer_id"], message="Пришлите ссылку на альбом VK без лишних символов формата https://vk.com/album-1234_5678", random_id=0)


async def set_remote_link(event):
    try:
        owner, album = int(event.message["text"].split("_")[0].split(
            "-")[1]), int(event.message["text"].split("_")[1])
    except:
        vk.messages.send(
            peer_id=event.message["peer_id"], message="Ссылка невалидна.", random_id=0)
        return
    document = database.find_document(database.teams, {
                                      "admin_id": event.message["from_id"], "personal": True, "source": "remote"})
    if not document:
        vk.messages.send(
            peer_id=event.message["peer_id"], message="Сначала начните игру и выберите источник.", random_id=0)
        return
    database.update_document(database.teams, {"admin_id": event.message["from_id"], "personal": True}, {
                             "source_url": event.message["text"]})
    keyboard = VkKeyboard(one_time=True)
    keyboard.add_button(
        f"Начать одиночную игру", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button(
        f"Расформировать команду", color=VkKeyboardColor.NEGATIVE)
    keyboard = keyboard.get_keyboard()
    vk.messages.send(
        peer_id=event.message["peer_id"], message="Новый альбом установлен.", random_id=0, keyboard=keyboard)


async def leave_team_cb(event):
    uid = event.message["from_id"]
    document = database.find_document(
        database.teams, {"users": {"$all": [uid]}})
    name = vk.users.get(user_ids=uid)[0]
    name = name["first_name"] + " " + name["last_name"]
    if not document:
        vk.messages.send(
            peer_id=event.message["peer_id"], message="Вы не являетесь участником ни одной команды.", random_id=0)
        return
    if document["admin_id"] == uid:
        vk.messages.send(
            peer_id=event.message["peer_id"], message=f"Вы покинули команду \"{document['team_name']}\". Поскольку вы ее администратор, команда расформирована.", random_id=0)
        for user in document["users"]:
            if user == uid:
                continue
            print("print", user)
            vk.messages.send(
                peer_id=user, message=f"Администратор покинул команду \"{document['team_name']}\", поэтому она была расформирована.", random_id=0)
        database.delete_document(database.teams, {"admin_id": uid})
        return
    vk.messages.send(
        peer_id=event.message["peer_id"], message=f"Вы покинули команду \"{document['team_name']}\".", random_id=0)
    document["users"].remove(uid)
    database.update_document(database.teams, {"users": {"$all": [uid]}}, {
                             "users": document["users"]})
    for user in document["users"]:
        vk.messages.send(
            peer_id=user, message=f"Пользователь @id{uid} ({name}) покинул игру.", random_id=0)


async def remove_team_cb(event):
    uid = event.message["from_id"]
    document = database.find_document(
        database.teams, {"admin_id": uid, "personal": False})
    if not document:
        vk.messages.send(
            peer_id=event.message["peer_id"], message="Вы не администрируете ни одной команды. Возможно, вы хотите покинуть текущую команду?", random_id=0)
        return
    for user in document["users"]:
        if user == uid:
            vk.messages.send(
                peer_id=event.message["peer_id"], message=f"Команда \"{document['team_name']}\" расформирована.", random_id=0)
            continue
        vk.messages.send(
            peer_id=user, message=f"Команда \"{document['team_name']}\", в которой вы находились, была расформирована.", random_id=0)
    database.delete_document(
        database.teams, {"admin_id": uid, "personal": False})
    if document["game_state"]["active"]:
        database.delete_document(
            database.teams_values, {"tid": document["team_name"]})


async def join_team_cb(event):
    uid = event.message["from_id"]
    team_id, command = [x[::-1]
                        for x in event.message["text"][::-1].split(maxsplit=1)]
    document = database.find_document(
        database.teams, {"invite": team_id, "personal": False})
    if not document:
        vk.messages.send(
            peer_id=event.message["peer_id"], message="Такой команды не существует: возожно, у вас опечатка или команда была расформирована.", random_id=0)
        return
    if uid in document["users"]:
        vk.messages.send(
            peer_id=event.message["peer_id"], message="Вы уже в команде.", random_id=0)
        return
    name = vk.users.get(user_ids=uid)[0]
    name = name["first_name"] + " " + name["last_name"]
    new_users = document["users"] + [uid]
    new_users_state = document["game_state"]
    new_users_state["users_state"] += [{"uid": uid, "score": 0}]
    database.update_document(database.teams, {"invite": team_id, "personal": False}, {
                             "users": new_users, "game_state": new_users_state})
    for user in new_users:
        print(user, uid)
        if user == uid:
            vk.messages.send(
                peer_id=event.message["peer_id"], message=f"Вы успешно присоединились к команде \"{document['team_name']}\".", random_id=0)
            continue
        if user == document["admin_id"] and len(new_users)>1:
            keyboard = VkKeyboard(one_time=True)
            keyboard.add_button(
                f"Начать мультиплеер", color=VkKeyboardColor.POSITIVE)
            keyboard.add_line()
            keyboard.add_button(f"Расформировать команду",
                                color=VkKeyboardColor.NEGATIVE)
            keyboard = keyboard.get_keyboard()
            vk.messages.send(
            peer_id=document["admin_id"], message=f"В команде {len(new_users)} человек, можно начинать мультиплеер!", random_id=0, keyboard=keyboard)
        vk.messages.send(
            peer_id=user, message=f"В команде новый игрок, прошу любить и жаловать, - @id{uid} ({name})!", random_id=0)


async def start_oneplayer_game_cb(event):
    document = database.find_document(
        database.teams, {"admin_id": event.message["from_id"], "personal": True})
    if not document:
        vk.messages.send(
            peer_id=event.message["peer_id"], message=f"Вы не состоите в одиночной игре.", random_id=0)
        return
    if document["game_state"]["active"]:
        vk.messages.send(
            peer_id=event.message["peer_id"], message=f"Игра уже начата. Вы хотите ее закончить?", random_id=0)
        return
    cur_state = document["game_state"]
    cur_state["active"] = True
    database.update_document(database.teams, {
                             "admin_id": event.message["from_id"], "personal": True}, {"game_state": cur_state})
    vk.messages.send(
        peer_id=event.message["peer_id"], message=f"Игра началась!", random_id=0)
    oneplayer_tick(event.message["from_id"])
    

async def start_multiplayer_game_cb(event):
    document = database.find_document(
        database.teams, {"admin_id": event.message["from_id"], "personal": False})
    if not document:
        vk.messages.send(
            peer_id=event.message["peer_id"], message=f"Вы не состоите в мультиплеере.", random_id=0)
        return
    if document["game_state"]["active"]:
        vk.messages.send(
            peer_id=event.message["peer_id"], message=f"Игра уже начата. Вы хотите ее закончить?", random_id=0)
        return
    cur_state = document["game_state"]
    cur_state["active"] = True
    database.update_document(database.teams, {
                             "admin_id": event.message["from_id"], "personal": False}, {"game_state": cur_state})
    vk.messages.send(
        peer_id=event.message["peer_id"], message=f"Игра началась!", random_id=0)
    multiplayer_tick(event.message["from_id"])


def oneplayer_tick(uid):
    document = database.find_document(
        database.teams, {"admin_id": uid, "personal": True})
    if not document:
        return
    source = document["source"]
    if source == "default":
        images, indices, overlist = generate_local_image(uid, 5, 0, True)
        signs = [get_current_sign(f"{indices[i]}.jpg", "default").split()
                 for i in range(0, len(images)-1)]
        signs_line = []

        for sign in signs:
            for s in sign:
                signs_line.append(s)
        signs_line = list(set(signs_line))
        for sign in signs_line:
            e = 0
            where = []
            for image_caption in signs:
                if sign in image_caption:
                    e += 1
                    where.append(signs.index(image_caption))
            if e < 2:
                break
        keyboard = VkKeyboard(one_time=True)
        keyboard.add_button(
            f"1", color=VkKeyboardColor.SECONDARY)
        keyboard.add_button(
            f"2", color=VkKeyboardColor.SECONDARY)
        keyboard.add_button(
            f"3", color=VkKeyboardColor.SECONDARY)
        keyboard.add_button(
            f"4", color=VkKeyboardColor.SECONDARY)
        keyboard.add_button(
            f"5", color=VkKeyboardColor.SECONDARY)
        keyboard.add_line()
        keyboard.add_button(f"Закончить игру",
                            color=VkKeyboardColor.NEGATIVE)
        keyboard = keyboard.get_keyboard()
        new_state = document["game_state"]
        new_state["users_state"][0]["right_answer"] = where[0] + 1
        database.update_document(database.teams, {"admin_id": uid, "personal": True}, {
                                 "game_state": new_state})
        vk.messages.send(peer_id=uid, message=f"Ключевое слово - {sign}", attachment=",".join(
            images), random_id=0, keyboard=keyboard)
    if source == "another":
        images, indices, overlist = generate_local_image(uid, 5, 0, True)
        signs = [get_current_sign(f"{indices[i]}.jpg", "another").split()
                 for i in range(0, len(images)-1)]
        signs_line = []

        for sign in signs:
            for s in sign:
                signs_line.append(s)
        signs_line = list(set(signs_line))
        for sign in signs_line:
            e = 0
            where = []
            for image_caption in signs:
                if sign in image_caption:
                    e += 1
                    where.append(signs.index(image_caption))
            if e < 2:
                break
        keyboard = VkKeyboard(one_time=True)
        keyboard.add_button(
            f"1", color=VkKeyboardColor.SECONDARY)
        keyboard.add_button(
            f"2", color=VkKeyboardColor.SECONDARY)
        keyboard.add_button(
            f"3", color=VkKeyboardColor.SECONDARY)
        keyboard.add_button(
            f"4", color=VkKeyboardColor.SECONDARY)
        keyboard.add_button(
            f"5", color=VkKeyboardColor.SECONDARY)
        keyboard.add_line()
        keyboard.add_button(f"Закончить игру",
                            color=VkKeyboardColor.NEGATIVE)
        keyboard = keyboard.get_keyboard()
        new_state = document["game_state"]
        new_state["users_state"][0]["right_answer"] = where[0] + 1
        database.update_document(database.teams, {"admin_id": uid, "personal": True}, {
                                 "game_state": new_state})
        vk.messages.send(peer_id=uid, message=f"Ключевое слово - {sign}", attachment=",".join(
            images), random_id=0, keyboard=keyboard)
    if source == "remote":
        images, captions, overlist = generate_remote_image(uid, 5, 0)
        # print(images)
        # print(captions)
        captions = [captions[image].split() for image in images]
        print(captions)
        
        signs = captions
        signs_line = []

        for sign in signs:
            for s in sign:
                signs_line.append(s)
        signs_line = list(set(signs_line))
        for sign in signs_line:
            e = 0
            where = []
            for image_caption in signs:
                if sign in image_caption:
                    e += 1
                    where.append(signs.index(image_caption))
            if e < 2:
                break
        keyboard = VkKeyboard(one_time=True)
        keyboard.add_button(
            f"1", color=VkKeyboardColor.SECONDARY)
        keyboard.add_button(
            f"2", color=VkKeyboardColor.SECONDARY)
        keyboard.add_button(
            f"3", color=VkKeyboardColor.SECONDARY)
        keyboard.add_button(
            f"4", color=VkKeyboardColor.SECONDARY)
        keyboard.add_button(
            f"5", color=VkKeyboardColor.SECONDARY)
        keyboard.add_line()
        keyboard.add_button(f"Закончить игру",
                            color=VkKeyboardColor.NEGATIVE)
        keyboard = keyboard.get_keyboard()
        new_state = document["game_state"]
        new_state["users_state"][0]["right_answer"] = where[0] + 1
        database.update_document(database.teams, {"admin_id": uid, "personal": True}, {
                                 "game_state": new_state})
        vk.messages.send(peer_id=uid, message=f"Ключевое слово - {sign}", attachment=",".join(
            images), random_id=0, keyboard=keyboard)
        
def multiplayer_tick(uid):
    document = database.find_document(
        database.teams, {"admin_id": uid, "personal": False})
    if not document:
        return
    source = document["source"]
    if source == "default":
        images, indices, overlist = generate_local_image(uid, 5, 0, True)
        signs = [get_current_sign(f"{indices[i]}.jpg", "default").split()
                 for i in range(0, len(images)-1)]
        signs_line = []

        for sign in signs:
            for s in sign:
                signs_line.append(s)
        signs_line = list(set(signs_line))
        for sign in signs_line:
            e = 0
            where = []
            for image_caption in signs:
                if sign in image_caption:
                    e += 1
                    where.append(signs.index(image_caption))
            if e < 2:
                break
        keyboard = VkKeyboard(one_time=True)
        keyboard.add_button(
            f"1", color=VkKeyboardColor.SECONDARY)
        keyboard.add_button(
            f"2", color=VkKeyboardColor.SECONDARY)
        keyboard.add_button(
            f"3", color=VkKeyboardColor.SECONDARY)
        keyboard.add_button(
            f"4", color=VkKeyboardColor.SECONDARY)
        keyboard.add_button(
            f"5", color=VkKeyboardColor.SECONDARY)
        keyboard.add_line()
        keyboard.add_button(f"Покинуть команду",
                            color=VkKeyboardColor.NEGATIVE)
        keyboard = keyboard.get_keyboard()
        new_state = document["game_state"]
        print(new_state)
        for i in range(0, len(new_state["users_state"])):
            print(i)
            new_state["users_state"][i]["right_answer"] = where[0] + 1
            new_state["users_state"][i]["ready"] = False
            vk.messages.send(peer_id=new_state["users_state"][i]["uid"], message=f"Ключевое слово - {sign}", attachment=",".join(
            images), random_id=0, keyboard=keyboard)
        database.update_document(database.teams, {"admin_id": uid, "personal": False}, {
                                 "game_state": new_state})
    if source == "another":
        images, indices, overlist = generate_local_image(uid, 5, 0, True)
        signs = [get_current_sign(f"{indices[i]}.jpg", "another").split()
                 for i in range(0, len(images)-1)]
        signs_line = []

        for sign in signs:
            for s in sign:
                signs_line.append(s)
        signs_line = list(set(signs_line))
        for sign in signs_line:
            e = 0
            where = []
            for image_caption in signs:
                if sign in image_caption:
                    e += 1
                    where.append(signs.index(image_caption))
            if e < 2:
                break
        keyboard = VkKeyboard(one_time=True)
        keyboard.add_button(
            f"1", color=VkKeyboardColor.SECONDARY)
        keyboard.add_button(
            f"2", color=VkKeyboardColor.SECONDARY)
        keyboard.add_button(
            f"3", color=VkKeyboardColor.SECONDARY)
        keyboard.add_button(
            f"4", color=VkKeyboardColor.SECONDARY)
        keyboard.add_button(
            f"5", color=VkKeyboardColor.SECONDARY)
        keyboard.add_line()
        keyboard.add_button(f"Покинуть команду",
                            color=VkKeyboardColor.NEGATIVE)
        keyboard = keyboard.get_keyboard()
        new_state = document["game_state"]
        for i in range(0, len(new_state["users_state"])):
            new_state["users_state"][i]["right_answer"] = where[0] + 1
            new_state["users_state"][i]["ready"] = False
            vk.messages.send(peer_id=new_state["users_state"][i]["uid"], message=f"Ключевое слово - {sign}", attachment=",".join(
            images), random_id=0, keyboard=keyboard)
        database.update_document(database.teams, {"admin_id": uid, "personal": False}, {
                                 "game_state": new_state})
    if source == "remote":
        images, captions, overlist = generate_remote_image(uid, 5, 0)
        captions = [captions[image].split() for image in images]
        
        signs = captions
        signs_line = []

        for sign in signs:
            for s in sign:
                signs_line.append(s)
        signs_line = list(set(signs_line))
        for sign in signs_line:
            e = 0
            where = []
            for image_caption in signs:
                if sign in image_caption:
                    e += 1
                    where.append(signs.index(image_caption))
            if e < 2:
                break
        keyboard = VkKeyboard(one_time=True)
        keyboard.add_button(
            f"1", color=VkKeyboardColor.SECONDARY)
        keyboard.add_button(
            f"2", color=VkKeyboardColor.SECONDARY)
        keyboard.add_button(
            f"3", color=VkKeyboardColor.SECONDARY)
        keyboard.add_button(
            f"4", color=VkKeyboardColor.SECONDARY)
        keyboard.add_button(
            f"5", color=VkKeyboardColor.SECONDARY)
        keyboard.add_line()
        keyboard.add_button(f"Закончить игру",
                            color=VkKeyboardColor.NEGATIVE)
        keyboard = keyboard.get_keyboard()
        new_state = document["game_state"]
        for i in range(0, len(new_state["users_state"])):
            new_state["users_state"][i]["ready"] = False
            vk.messages.send(peer_id=new_state["users_state"][i]["uid"], message=f"Ключевое слово - {sign}", attachment=",".join(
            images), random_id=0, keyboard=keyboard)
        database.update_document(database.teams, {"admin_id": uid, "personal": False}, {
                                 "game_state": new_state})


async def oneplayer_handler_cb(event):
    uid = event.message["from_id"]
    document = database.find_document(
        database.teams, {"admin_id": uid, "personal": True})
    if not document:
        return
    text = event.message["text"]
    if text == "Закончить игру":
        score = document["game_state"]["users_state"][0]["score"]
        vk.messages.send(
            peer_id=uid, message=f"Вы закончили одиночную игру! Ваш результат - {score} баллов.", random_id=0)
        return
    if text in ["1", "2", "3", "4", "5"]:
        right_answer = document["game_state"]["users_state"][0]["right_answer"]
        score = document["game_state"]["users_state"][0]["score"]
        answer = int(text)
        if answer == right_answer:
            vk.messages.send(
                peer_id=uid, message=f"Поздравляем, ответ верный! Вы получаете +3 балла.", random_id=0)
            score += 3
        else:
            vk.messages.send(
                peer_id=uid, message=f"Сожалею, вы ошиблись и не получаете баллов.", random_id=0)
        new_state = document["game_state"]
        new_state["users_state"][0]["score"] = score
        database.update_document(database.teams, {"admin_id": uid, "personal": True}, {
                                 "game_state": new_state})
        oneplayer_tick(uid)

    else:
        vk.messages.send(
            peer_id=uid, message=f"Ваш ответ - число от 1 до 5.", random_id=0)
        
async def multiplayer_handler_cb(event):
    uid = event.message["from_id"]
    document = database.find_document(
        database.teams, {"users": {"$all": [uid]}, "personal": False})
    if not document:
        return
    new_state = document["game_state"]
    text = event.message["text"]
    if text == "Покинуть команду":
        score = document["game_state"]["users_state"][0]["score"]
        vk.messages.send(
            peer_id=uid, message=f"Вы покинули команду и закончили игру. Ваш результат - {score} баллов.", random_id=0)
        users = document["users"]
        users.remove(uid)
        for u in range(0, len(new_state["users_state"])):
            if new_state["users_state"][u]["uid"] == uid:
                new_state["users_state"].remove(new_state["users_state"][u])
                break
        document = database.update_document(
        database.teams, {"users": {"$all": [uid]}, "personal": False}, {"users": users, "game_state": new_state})
        return
    if text in ["1", "2", "3", "4", "5"]:
        right_answer = document["game_state"]["users_state"][0]["right_answer"]
        all_ready = 0
        for u in range(0, len(new_state["users_state"])):
            if new_state["users_state"][u]["uid"] == uid:
                score = document["game_state"]["users_state"][u]["score"]
                answer = int(text)
                if answer == right_answer:
                    vk.messages.send(
                        peer_id=uid, message=f"Поздравляем, ответ верный! Вы получаете +3 балла.", random_id=0)
                    score += 3
                else:
                    vk.messages.send(
                        peer_id=uid, message=f"Сожалею, вы ошиблись и не получаете баллов.", random_id=0)
                new_state["users_state"][u]["score"] = score
                new_state["users_state"][u]["ready"] = True
                database.update_document(database.teams, {"users": {"$all": [uid]}, "personal": False}, {
                                        "game_state": new_state})
                all_ready += 1
            elif new_state["users_state"][u]["ready"]:
                all_ready += 1
        for k in range(0, len(new_state["users_state"])):
            if new_state["users_state"][k]["score"] >= 40:
                name = vk.users.get(user_ids=document["game_state"]["users_state"][k]["uid"])[0]
                name = name["first_name"] + " " + name["last_name"]
                for h in range(0, len(new_state["users_state"])):
                    vk.messages.send(peer_id=new_state["users_state"][h]["uid"], message=f'Игра окончена! Победитель @id{new_state["users_state"][k]["uid"]} ({name}) с {new_state["users_state"][k]["score"]} очками.', random_id=0)
                database.delete_document(database.teams, {"users": {"$all": [new_state["users_state"][k]["uid"]]}})
                break
        if all_ready == len(new_state["users_state"]):
            multiplayer_tick(document["admin_id"])
            
        

    else:
        vk.messages.send(
            peer_id=uid, message=f"Ваш ответ - число от 1 до 5.", random_id=0)


async def start_single_game_cb(event):
    # играет один человек на баллы без потолка
    team_name = "Одиночная игра"
    team = create_team(event.message["peer_id"],
                       event.message["from_id"], True, team_name, "oneplayer", "oneplayer")
    keyboard = VkKeyboard(one_time=True)
    keyboard.add_button(
        f"От организаторов Вездекода ●", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button(
        f"От MurTeam ●", color=VkKeyboardColor.POSITIVE)
    keyboard.add_line()
    keyboard.add_button(f"Ссылка на альбом VK ●",
                        color=VkKeyboardColor.PRIMARY)
    keyboard = keyboard.get_keyboard()

    vk.messages.send(
        peer_id=event.message["peer_id"], message=f"Выберите источник для одиночной игры.", random_id=0, keyboard=keyboard)

    # if not document:
    #     vk.messages.send(
    #         peer_id=event.message["peer_id"], message="Вы не являетесь учатсником ни одной игры.", random_id=0)
    #     return
    # if uid != document["admin_id"]:
    #     vk.messages.send(
    #         peer_id=event.message["peer_id"], message="Начать игру может только администратор.")


async def view_results_cb(event):
    document = database.find_document(database.teams, {"users": {"$all": [event.message["from_id"]]}})
    if not document:
        vk.messages.send(
        peer_id=event.message["peer_id"], message=f"Вы не участник игры...(", random_id=0)
        return
    result = "Результаты:\n"
    for i in range(0, len(document["game_state"]["users_state"])):
        name = vk.users.get(user_ids=document["game_state"]["users_state"][i]["uid"])[0]
        name = name["first_name"] + " " + name["last_name"]
        res = f'''
        @id{document["game_state"]["users_state"][i]["uid"]} ({name}) {"(исключён)" if document["game_state"]["users_state"][i]["uid"] not in document["users"] else ""} - {document["game_state"]["users_state"][i]["score"]} баллов\n
        '''
        result += res
    vk.messages.send(
            peer_id=event.message["peer_id"], message=result, random_id=0)

async def view_games_cb(event):
    games = database.find_document(database.teams, {}, True)
    result = ""
    _games = False
    for game in games:
        if game["personal"]: continue
        _games = True
        # одиночные игры скрываем
        res = f"Игра {game['invite']} | {len(game['users'])} человек | {'мультиплеер' if game['mode'] == 'multiplayer' else 'с ведущим'}\n" 
        result += res
    result += "Чтобы присоединиться к команде, напишите \"Присоединиться к <код>\", например \"Присоединиться к 1234\"."
    if not _games:
        result = "Нет открытых игр. Создайте свою командой \"Создать команду <имя>\"!"
    vk.messages.send(peer_id=event.message["peer_id"], message=result, random_id=0)
        
async def help_cb(event):
    # первое сообщение и сообщение помощи
    text = f'''
    Привет!
    Это Имаджинариум в виде чат-бота от команды MurTeam на @vezdekod (Вездекоде)`22.
    По любым вопросам: @superdev
    Режимы игр:
    - "старт" - генерация 5-ти случайных неповторяющихся (для вас) картинок (бот на 10 баллов);
    - "на баллы" - режим отгадывания картинки по заданному слову в one-плеере. Правильный ответ - +3 балла, неправильный - 0 (бот на 20 баллов);
    - "мультиплеер" - выбирайте собранную команду и играйте с ней, или создайте свою! (бот на 40 баллов);
    - "мультиплеер с ведущим" - мультиплеер по всем правилам Имаджинариума с ведущим (бот на 50 баллов);
    Есть возможность добавить свой источник игры (альбом VK) и выбрать его в своей команде. По умолчанию источника два - выданный организаторами датасет с дефолтными подписями и этот же датасет, но с разметкой от команды разработчиков.
    '''
    keyboard = VkKeyboard(one_time=True)
    # False Если клавиатура должна оставаться откртой после нажатия на кнопку
    # True если она должна закрваться

    keyboard.add_button("Старт", color=VkKeyboardColor.SECONDARY)

    keyboard.add_line()  # Обозначает добавление новой строки
    keyboard.add_button("На баллы", color=VkKeyboardColor.SECONDARY)
    keyboard.add_line()  # Обозначает добавление новой строки
    keyboard.add_button("Игры", color=VkKeyboardColor.POSITIVE)
    keyboard.add_line()  # Обозначает добавление новой строки
    keyboard.add_button("Создать команду", color=VkKeyboardColor.PRIMARY)

    keyboard = keyboard.get_keyboard()
    vk.messages.send(
        peer_id=event.message["peer_id"], random_id=0, message=text, keyboard=keyboard)

'''

Асинхронная обертка для библиотеки vk_api без подержки асинхронности.
Автор: vk.com/superdev
Функция MessageHandler обрабатывает входящее событие, проверяет, является ли оно сообщением, а также применяет указанный фильтр в виде регулярного выражения. Если событие подходит под заданные параметры (хэндлер), то функция возвращает True и событие передается требуемой корутине, иначе возвращает False.
В функции dispatch определяются хэндлеры и запускаемые ими функции.
Каждое событие из longpoll передается функции-диспетчеру, которая распределяет нужные события по командам практически моментально, что обеспечивает асинхронность обработки событий.
'''


def MessageHandler(event, regexp):
    if event.type != VkBotEventType.MESSAGE_NEW:
        return False
    if len(re.findall(regexp, event.message.get("text", ""))) > 0:
        return True
    return False


async def dispatch(event):
    if MessageHandler(event, r"(?i)^(пинг|бот чек)"):
        asyncio.create_task(check_cb(event))
        return
    if MessageHandler(event, r"(?i)^(начать|привет|помощь|хелп)$"):
        asyncio.create_task(help_cb(event))
        return
    if MessageHandler(event, r"(?i)^(привет|хелло)"):
        asyncio.create_task(hello_cb(event))
        return
    if MessageHandler(event, r"(?i)^(старт)"):
        asyncio.create_task(image_cb(event))
        return
    if MessageHandler(event, r"(?i)^(настройка подписей локальных изображений)"):
        asyncio.create_task(start_sign_cb(event))
        return
    if MessageHandler(event, r"(?i)^(на баллы)"):
        asyncio.create_task(start_single_game_cb(event))
        return
    if MessageHandler(event, r"(?i)^(создать команду)"):
        asyncio.create_task(create_team_cb(event))
        return
    if MessageHandler(event, r"(?i)^(мультиплеер \d+|мультиплеер с ведущим \d+)"):
        asyncio.create_task(change_multiplayer_mode_cb(event))
        return
    if MessageHandler(event, r"(?i)^(https://vk.com/)"):
        asyncio.create_task(set_remote_link(event))
        return
    if MessageHandler(event, r"(?i)^(от организаторов вездекода ●|ссылка на альбом VK ●|от murteam ●)"):
        asyncio.create_task(change_oneplayer_mode_cb(event))
        return
    if MessageHandler(event, r"(?i)^(начать одиночную игру)"):
        asyncio.create_task(start_oneplayer_game_cb(event))
        return
    if MessageHandler(event, r"(?i)^(начать мультиплеер)"):
        asyncio.create_task(start_multiplayer_game_cb(event))
        return
    if MessageHandler(event, r"(?i)^(покинуть команду)"):
        asyncio.create_task(leave_team_cb(event))
        return
    if MessageHandler(event, r"(?i)^(расформировать команду)"):
        asyncio.create_task(remove_team_cb(event))
        return
    if MessageHandler(event, r"(?i)^(присоединиться к \d+)"):
        asyncio.create_task(join_team_cb(event))
        return
    if MessageHandler(event, r"(?i)^(результаты)"):
        asyncio.create_task(view_results_cb(event))
        return
    if MessageHandler(event, r"(?i)^(игры)"):
        asyncio.create_task(view_games_cb(event))
        return

    if MessageHandler(event, r"(?i)^(.)"):
        asyncio.create_task(sign_handler_cb(event))
    if MessageHandler(event, r"(?i)^(.)"):
        asyncio.create_task(oneplayer_handler_cb(event))
    if MessageHandler(event, r"(?i)^(.)"):
        asyncio.create_task(multiplayer_handler_cb(event))

for event in longpoll.listen():
    print(event)
    loop = asyncio.get_event_loop()
    task = loop.create_task(dispatch(event))
    loop.run_until_complete(task)
