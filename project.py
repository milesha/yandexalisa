from flask import Flask, request
import logging
import requests
import json
from random import choice

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)

# изображения для путеводителя
cities = {
    'москва': ['1652229/f96dad746dbe46b6b350'],
    'сочи': ["965417/0cc63d864c4085a8ec13"],
    'санкт-петербург': ["1540737/5590e5b2bf2ae017563f"]
}

sessionStorage = {}


@app.route('/post', methods=['POST'])
def main():
    logging.info('Request: %r', request.json)
    response = {
        'session': request.json['session'],
        'version': request.json['version'],
        'response': {
            'end_session': False
        }
    }
    handle_dialog(response, request.json)
    logging.info('Response: %r', response)
    return json.dumps(response)


def handle_dialog(res, req):
    user_id = req['session']['user_id']
    # начало диалога для нового пользователя
    if req['session']['new']:
        res['response']['text'] = 'Привет! Назови своё имя!'
        res['response']['buttons'] = [
            {
                'title': 'Помощь',
                'hide': False
            }
        ]
        sessionStorage[user_id] = {
            'first_name': None,  # здесь будет храниться имя
            'game_started': False  # здесь информация о том, что пользователь начал игру. По умолчанию False
        }
        return

    if sessionStorage[user_id]['first_name'] is None:
        # помощь пользователю
        if req['request']['original_utterance'].lower() == 'помощь':
            res['response']['text'] = 'Я лицейский гид. Помогу тебе в составлении маршрутов в путешествие по России. ' \
                                      'Но для начала представься'
            res['response']['buttons'] = [
                {
                    'title': 'Помощь',
                    'hide': False
                }
            ]
            return

        first_name = get_first_name(req)
        if first_name is None:
            res['response']['text'] = 'Не расслышала имя. Повтори, пожалуйста!'

        else:
            sessionStorage[user_id]['first_name'] = first_name
            res['response']['text'] = f'Приятно познакомиться, {first_name.title()}. Я Алиса' \
                f' и по совместительству лицейский гид! ' \
                f'С моей помощью ты сможешь составить маршрут' \
                f' в путешествие по России.' \
                f' Для начала выбери город'

            # начальные значения для нового пользователя
            sessionStorage[user_id]['places'] = []  # список координат мест, которые выбрал пользователь
            # диалог преполагает несколько режимов
            # choose_city - выбор города, get_info - ожидание названия объекта от пользователя,
            # post_info - возвращение информации Алисой
            sessionStorage[user_id]['mode'] = 'choose_city'  # режим выбора города
            sessionStorage[user_id]['suggests_city'] = None  # подсказки для городов в путеводителе
            sessionStorage[user_id]['city'] = ''  # выбранный город
            sessionStorage[user_id]['suggests'] = [
                {
                    'title': 'Санкт-Петербург',
                    'hide': True
                },
                {
                    'title': 'Москва',
                    'hide': True
                },
                {
                    'title': 'Сочи',
                    'hide': True
                },
                {
                    'title': 'Помощь',
                    'hide': False
                }
            ]
            res['response']['buttons'] = sessionStorage[user_id]['suggests']
    else:
        # помощь пользователю
        if req['request']['original_utterance'].lower() == 'помощь':
            if sessionStorage[user_id]['mode'] == 'post_info':
                res['response']['buttons'] = sessionStorage[user_id]['suggests']
                res['response']['text'] = 'Ты можешь узнать номер телефона или часы работы организации,' \
                                          ' или мы можем продолжить составлять маршрут.'
            elif sessionStorage[user_id]['mode'] == 'get_info':
                res['response']['text'] = 'Скажи мне адрес, название или тип организации (аптека, магазин, парк),' \
                                          ' куда ты хочешь попасть.'
            elif sessionStorage[user_id]['mode'] == 'choose_city':
                res['response']['buttons'] = sessionStorage[user_id]['suggests']
                res['response']['text'] = 'Я помогу тебе составить маршрут для путешествия по России. ' \
                                          'Какой город ты хочешь посетить?'
            else:
                res['response']['text'] = 'Я помогу тебе составить идеальный маршрут для путешествия по России' \
                                          ' и нанесу все точки на Яндекс Карту, чтобы ты легко нашел путь!'
                res['response']['buttons'] = []
                if sessionStorage[user_id]['suggests_city']:
                    for item in sessionStorage[user_id]['suggests_city']:
                        res['response']['buttons'].append({
                            'title': item,
                            'hide': True
                        })
            return
        # возвращение конечной карты маршрута
        if req["request"]["original_utterance"].lower() == 'закончи составление маршрута' \
                and sessionStorage[user_id]['city']:

            if sessionStorage[user_id]['places']:
                url = get_url(sessionStorage[user_id]['places'])
                res['response']['text'] = f'Вот ссылка на маршрут на карте: {url}'
                res['end_session'] = True
                return
            else:
                res['response']['text'] = f'К сожалению, в твоем маршруте еще нет мест.' \
                    f'Куда ты хочешь отправиться?'
                return

        # режим выбора города
        if sessionStorage[user_id]['mode'] == 'choose_city':
            if get_city(req):
                if rus_city(get_city(req)):
                    sessionStorage[user_id]['city'] = get_city(req)
                    # обработка города из путеводителя
                    if get_city(req) in cities:
                        sessionStorage[user_id]['mode'] = 'get_info'
                        res['response']['card'] = {}
                        res['response']['card']['type'] = 'BigImage'
                        res['response']['card']['title'] = f'Отличный выбор! Мне нравится {get_city(req).title()}.' \
                            f' Куда ты хочешь отправиться?'
                        res['response']['card']['image_id'] = cities[get_city(req)][0]
                        res['response']['buttons'] = [
                            {
                                'title': 'Помощь',
                                'hide': False
                            }
                        ]
                        res['response']['text'] = 'Куда ты хочешь отправиться?'
                        if get_city(req) == 'москва':
                            sessionStorage[user_id]['suggests_city'] = ['Красная площадь', 'Третьяковская галерея',
                                                                        'Большой театр',
                                                                        'Александровский сад']
                            for item in sessionStorage[user_id]['suggests_city']:
                                res['response']['buttons'].append({
                                    'title': item,
                                    'hide': True
                                })
                        elif get_city(req) == 'сочи':
                            sessionStorage[user_id]['suggests_city'] = ['Собор Михаила Архангела', 'Роза Хутор',
                                                                        'Сочинский дендрарий',
                                                                        'Сочинский государственный цирк']
                            for item in sessionStorage[user_id]['suggests_city']:
                                res['response']['buttons'].append({
                                    'title': item,
                                    'hide': True
                                })
                        elif get_city(req) == 'санкт-петербург':
                            sessionStorage[user_id]['suggests_city'] = ['Государственный Эрмитаж', 'Спас на Крови',
                                                                        'Зимний дворец',
                                                                        'Петергоф']
                            for item in sessionStorage[user_id]['suggests_city']:
                                res['response']['buttons'].append({
                                    'title': item,
                                    'hide': True
                                })
                        return
                    # обработка города не из путеводителя
                    else:
                        sessionStorage[user_id]['mode'] = 'get_info'  # переключения режима диалога
                        res['response']['text'] = f'Отлично! Ты собираешься в {get_city(req).title()}, ' \
                            f'куда ты хочешь отправиться?'
                        res['response']['buttons'] = [
                            {
                                'title': 'Помощь',
                                'hide': False
                            }
                        ]
                        return
                # обработка некорректных запросов
                else:
                    res['response']['text'] = 'К сожалению, я не нашла такого города в России. Попробуй еще раз.'
                    res['response']['buttons'] = sessionStorage[user_id]['suggests']
                    return
            # обработка некорректных запросов
            else:
                res['response']['text'] = 'К сожалению, я не нашла такого города в России. Попробуй еще раз.'
                res['response']['buttons'] = sessionStorage[user_id]['suggests']
                return

        # режим получения названия объекта
        if sessionStorage[user_id]['mode'] == 'get_info':
            result = search(req['request']['original_utterance'].lower(),
                            sessionStorage[user_id]['city'])
            # при нахождении объекта в выбранном пункте
            if result["properties"]["ResponseMetaData"]["SearchResponse"]['found'] != 0:
                sessionStorage[user_id]['mode'] = 'post_info'
                sessionStorage[user_id]['places'].append(result["features"][0]["geometry"]["coordinates"])
                sessionStorage[user_id]['current_place'] = result["features"][0]
                res['response']['text'] = f'Хороший выбор! ' \
                    f'Я добавила {result["features"][0]["properties"]["CompanyMetaData"]["name"]}' \
                    f' в маршрут. Что дальше?'

                s = '+'.join(result["features"][0]["properties"]["CompanyMetaData"]["address"].split()) \
                    + "+" + '+'.join(result["features"][0]["properties"]["CompanyMetaData"]["name"].split())
                sessionStorage[user_id]['suggests'] = [
                    {
                        "title": "Покажи на карте",

                        "url": f'https://yandex.ru/maps/?mode=search&text='
                        f'{s}',
                        'hide': True
                    },
                    {
                        "title": "Назови часы работы",
                        "hide": True
                    },
                    {
                        "title": "Покажи номер телефона",
                        "hide": True
                    },
                    {
                        "title": "Добавь еще одно место",
                        "hide": True
                    },
                    {
                        "title": "Удали последнее место",
                        "hide": True
                    },
                    {
                        "title": "Закончи составление маршрута",
                        'url': get_url(sessionStorage[user_id]['places']),
                        "hide": True
                    },
                    {
                        "title": "Помощь",
                        "hide": False
                    },

                ]
                res['response']['buttons'] = sessionStorage[user_id]['suggests']
                copy = []
                if sessionStorage[user_id]['suggests_city']:
                    for i in sessionStorage[user_id]['suggests_city']:
                        copy.append(i.lower())
                    if req['request']['original_utterance'].lower() in copy:
                        sessionStorage[user_id]['suggests_city'].remove(req['request']['original_utterance'])
                return
            # обработка некорректных запросов
            else:
                res['response']['text'] = f'Кажется, что-то пошло не так. Я не нашла ' \
                    f'{req["request"]["original_utterance"].lower().title()}, ' \
                    f'попробуй выбрать другое место.'
                res['response']['buttons'] = [
                    {
                        'title': 'Помощь',
                        'hide': False
                    }
                ]
                if sessionStorage[user_id]['suggests_city']:
                    for item in sessionStorage[user_id]['suggests_city']:
                        res['response']['buttons'].append({
                            'title': item,
                            'hide': True
                        })
                return

        # режим возвращения запрашиваемой информации
        if sessionStorage[user_id]['mode'] == 'post_info':
            # возврат времени работы организации
            if req['request']['original_utterance'].lower() == 'Назови часы работы'.lower():
                # удаление времени работы органищации из подсказок
                sessionStorage[user_id]['suggests'] = remove_suggest(sessionStorage[user_id]['suggests'],
                                                                     'Назови часы работы')
                # сохранение нового споиска подсказок
                res['response']['buttons'] = sessionStorage[user_id]['suggests']
                try:
                    res['response']['text'] = f'Время работы ' \
                        f'{sessionStorage[user_id]["current_place"]["properties"]["CompanyMetaData"]["name"]}: ' \
                        f'{sessionStorage[user_id]["current_place"]["properties"]["CompanyMetaData"]["Hours"]["text"]}'
                # обработка ошибок
                except:
                    res['response']['text'] = 'Я не смогла найти часы работы. Хочешь узнать что-то еще?'
                return

            if req['request']['original_utterance'].lower() == 'Покажи номер телефона'.lower():
                # удаление номера телефона органищации из подсказок
                sessionStorage[user_id]['suggests'] = remove_suggest(sessionStorage[user_id]['suggests'],
                                                                     'Покажи номер телефона')
                # сохранение нового споиска подсказок
                res['response']['buttons'] = sessionStorage[user_id]['suggests']
                try:
                    phone = sessionStorage[user_id]["current_place"]["properties"
                    ]["CompanyMetaData"]["Phones"][0]["formatted"]
                    res['response']['text'] = f'Телефон ' \
                        f'{sessionStorage[user_id]["current_place"]["properties"]["CompanyMetaData"]["name"]}: ' \
                        f'{phone}'
                except:
                    res['response']['text'] = 'Я не смогла найти номер телефона . Хочешь узнать что-то еще?'
                return

            if req['request']['original_utterance'].lower() == 'Покажи на карте'.lower():
                # удаление показа органищации на карте из подсказок
                sessionStorage[user_id]['suggests'] = remove_suggest(sessionStorage[user_id]['suggests'],
                                                                     'Покажи на карте', True)
                # сохранение нового споиска подсказок
                res['response']['buttons'] = sessionStorage[user_id]['suggests']
                res['response']['text'] = f'Что дальше?'
                return

            if req['request']['original_utterance'].lower() == 'Удали последнее место'.lower():
                if sessionStorage[user_id]['suggests_city']:
                    sessionStorage[user_id]['suggests'] = [
                        {
                            "title": "Помощь",
                            "hide": False
                        }
                    ]
                    for item in sessionStorage[user_id]['suggests_city']:
                        sessionStorage[user_id]['suggests'].append({
                            'title': item,
                            'hide': True
                        })
                        res['response']['buttons'] = sessionStorage[user_id]['suggests']
                else:
                    sessionStorage[user_id]['suggests'] = [
                        {
                            "title": "Помощь",
                            "hide": False
                        }
                    ]
                    # сохранение нового споиска подсказок
                    res['response']['buttons'] = sessionStorage[user_id]['suggests']

                res['response']['text'] = f'Я удалила ' \
                    f'{sessionStorage[user_id]["current_place"]["properties"]["CompanyMetaData"]["name"]} ' \
                    f'из маршрута. Куда еще ты хочешь отправиться?'

                # удаление последней добавленной организации с карты
                sessionStorage[user_id]['places'] = \
                    sessionStorage[user_id]['places'][:(len(sessionStorage[user_id]['places']) - 1)]
                sessionStorage[user_id]['current_place'] = ''
                # переключаемся на режим выбора места
                sessionStorage[user_id]['mode'] = 'get_info'
                return

            if req['request']['original_utterance'].lower() == 'Добавь еще одно место'.lower():
                sessionStorage[user_id]['suggests'] = [
                    {
                        "title": "Помощь",
                        "hide": False
                    },
                    {
                        "title": "Закончи составление маршрута",
                        'url': get_url(sessionStorage[user_id]['places']),
                        "hide": True
                    },

                ]

                # сохранение нового споиска подсказок
                res['response']['buttons'] = sessionStorage[user_id]['suggests']
                if sessionStorage[user_id]['suggests_city']:
                    for item in sessionStorage[user_id]['suggests_city']:
                        res['response']['buttons'].append({
                            'title': item,
                            'hide': True
                        })

                res['response']['text'] = 'Куда еще ты хочешь отправиться?'
                # переключаемся на режим выбора места
                sessionStorage[user_id]['mode'] = 'get_info'
                return
            res['response']['text'] = choice(['Я тебя не понимаю, попробуй еще раз.',
                                              'Я тебя не расслышала, прости.',
                                              'Что ты сказал?'])
            res['response']['buttons'] = sessionStorage[user_id]['suggests']
            return


def remove_suggest(suggests, title, show=False):
    """
    Удаление подсказок для пользователя
    :param suggests: исходный список подсказок
    :param title: название удаляемой категории
    :param show: показ карты по url
    :return: новый список подсказок
    """
    for i in suggests:
        if i['title'] == title:
            if show:
                suggests.pop(0)
                break
            else:
                suggests.remove({"title": title, "hide": True})
                break
    return suggests


def get_city(req):
    # перебираем именованные сущности
    for entity in req['request']['nlu']['entities']:
        # если тип YANDEX.GEO, то пытаемся получить город(city), если нет, то возвращаем None
        if entity['type'] == 'YANDEX.GEO':
            # возвращаем None, если не нашли сущности с типом YANDEX.GEO
            return entity['value'].get('city', None)


def get_first_name(req):
    # перебираем сущности
    for entity in req['request']['nlu']['entities']:
        # находим сущность с типом 'YANDEX.FIO'
        if entity['type'] == 'YANDEX.FIO':
            # Если есть сущность с ключом 'first_name', то возвращаем её значение.
            # Во всех остальных случаях возвращаем None.
            return entity['value'].get('first_name', None)


def search(name, city):
    search_api_server = "https://search-maps.yandex.ru/v1/"
    api_key = "dda3ddba-c9ea-4ead-9010-f43fbc15c6e3"

    address_ll = "37.588392,55.734036"

    text = city + ', ' + name
    search_params = {
        "apikey": api_key,
        "text": text,
        "lang": "ru_RU",
        "ll": address_ll,
        "type": "biz"
    }

    response = requests.get(search_api_server, params=search_params)
    if not response:
        return None
    copy = response.json()
    return copy if copy else None


def get_url(places):
    '''
    Возвращение ссылки на static map
    :param places: метки, которые надо добавить на карту
    :return: ссылку на static map
    '''
    url = 'https://static-maps.yandex.ru/1.x/?l=map&pt='
    for i in range(len(places)):
        item = places[i]
        a1, a2 = str(item[0]), str(item[1])
        url += a1 + ',' + a2 + ',pm2lbl' + str(i + 1) + '~'
    url = url.rstrip('~')
    return url


def rus_city(city):
    # Готовим запрос.
    geocoder_request = f"http://geocode-maps.yandex.ru/1.x/?geocode={city}&format=json"

    # Выполняем запрос.
    response = None
    try:
        response = requests.get(geocoder_request)
        if response:
            # Запрос успешно выполнен, печатаем полученные данные.
            json_response = response.json()
            if json_response["response"]["GeoObjectCollection"]["featureMember"][0]["GeoObject"]['metaDataProperty'][
                'GeocoderMetaData']['Address']['Components'][0]['name'] == 'Россия':
                return True
            else:
                return False
        else:
            return False
    except:
        return False


if __name__ == '__main__':
    app.run()
