# import threading
import lxml.html as xhtml
import urllib.request
import urllib.error
import urllib.parse
import uuid
import datetime
import time
import json
import priceview_db

# базовый URL сайта
storeURL = 'http://www.mvideo.ru'
# идентификатор магазина
glStoreId = 1
glFldId = 0


def get_http_opener():
    opener = urllib.request.build_opener(urllib.request.HTTPRedirectHandler)
    opener.addheaders.append(("Cookie", "MVID_CITY_ID=CityCZ_15556; MVID_REGION_ID=89"))
    opener.addheaders.append(("User-Agent", "Mozilla/" + str(uuid.uuid4())))
    return opener


def get_list(obj, xpath):
    return obj.xpath(xpath)


def get_first(obj, xpath):
    first = None
    elem_list = obj.xpath(xpath)
    while len(elem_list):
        first = elem_list.pop()
    return first


def correct_text(byte_text):
    text = bytearray(byte_text)
    start = 0
    while True:

        start = text.find(b'data-product-info="{', start)
        if start == -1:
            break

        start = start + 20

        end = text.find(b'}"', start)
        if end == -1:
            break

        # замена кавычки, апострофа, слеша на пробел
        for idx in range(start, end):
            if text[idx] in b'"\'\\\n\r':
                text[idx] = ord(' ')
            elif text[idx:idx + 6] == b'&#034;':
                text[idx:idx + 5] = bytearray(b'      ')

        start = end + 2
    return bytes(text)


def skip_link(str_link):
    if str_link.find('from=hub') != -1:
        return True
    elif str_link.find('reff=reviews') != -1:
        return True
    else:
        return False


def load_prods(pid, link):

    global db
    global glFldId

    page_url = urllib.parse.urljoin(storeURL, link)
    is_first_page = True

    # цикл чтения неопреденного числа страниц
    while True:

        print(page_url)

        # чтение страници и преобразовнаие в xml
        try:
            opener = get_http_opener()
            response = opener.open(page_url)
        except urllib.error.HTTPError:
            # 404
            break

        html_text = response.read()
        page = xhtml.fromstring(correct_text(html_text))
        # page = xhtml.parse(page_url)

        if is_first_page:
            # на странице кроме товаров могут быть вложенные группы
            # обработаем сначала их
            # выборка запросом списка вложенных групп
            folders = get_list(page, '//div[@class="o-article-list"]/div[@class="o-article-list__item"]//a[contains(@class,"title-link")]')
            for folder_link in folders:
                data_link = folder_link.attrib['href']
                data_text = folder_link.text_content().strip()
                if skip_link(data_link):
                    continue
                glFldId = glFldId + 1
                db.insert_data_group({
                    "sid":   glStoreId,
                    "pid": pid,
                    "id": glFldId,
                    "name": data_text,
                    "link": data_link
                })
                load_prods(glFldId, data_link)

        # прочитаем все товары на странице
        # а если есть следующая страница, то перейдем к чтении ее
        prods_array = []
        joins_array = []

        # выборка запросом списка продуктов
        prods = get_list(page, '//div[contains(@class,"product-tiles-list")]/div[contains(@class,"product-tile")]//a[contains(@class,"product-tile-title-link")]')
        for prod_link in prods:
            data_link = prod_link.attrib['href']

            # у линка должен быть атрибут с данными продукта:
            product_info_str = prod_link.attrib['data-product-info']
            # print(product_info_str)
            product_info = json.loads(product_info_str)

            data_id = product_info['productId']  # ИД
            data_price = product_info['productPriceLocal']  # цена
            data_name = product_info['productName']  # наименование
            data_category = product_info['productCategoryName']  # категория
            data_vendor = product_info['productVendorName']  # производитель

            if data_id is None or data_price is None or data_name is None or data_id == '' or data_price == '' or data_name == '':
                continue

            prods_array.append({
                "sid": glStoreId,
                "id": data_id,
                "price": float(data_price),
                "name": data_name,
                "category": data_category,
                "vendor": data_vendor,
                "link": data_link
            })
            joins_array.append({
                "sid": glStoreId,
                "prod": data_id,
                "grp": pid
            })

        if len(prods_array):
            db.insert_prods(prods_array, joins_array)

        next_page_link = get_first(page, '//li[@class="pagination-item active"]/following-sibling::*//a')
        if next_page_link is not None:
            # есть следующая страница, продолжаем цикл чтения страниц
            page_url = urllib.parse.urljoin(storeURL, next_page_link.attrib['href'])
            is_first_page = False
            continue  # переход к чтению следующей страницы

        break  # while True


def load_catalog(catalog_link):

    global db
    global glFldId

    # чтение страници и преобразовнаие в xml
    opener = get_http_opener()
    page = xhtml.fromstring(opener.open(catalog_link).read())
    data_pid0 = 0

    # Группы уровня 1
    top_groups = get_list(page, '//div[@class="header-nav-wrap"]//ul[contains(@class,"header-nav-list")]/li[contains(@class,"header-nav-item")]')
    for topGroup in top_groups:

        # группа
        item_link = get_first(topGroup, 'a[contains(@class,"header-nav-item-link")]')
        if item_link is not None:
            data_link = item_link.attrib['href']
            if skip_link(data_link):
                continue

            item_text = get_first(item_link, './/span[contains(@class,"header-nav-item-text")]')
            if item_text is not None:
                date_text = item_text.text_content().strip()
                if date_text == 'Акции':  # Акции пропускаем
                    continue
                glFldId = glFldId + 1
                db.insert_data_group({
                    "sid": glStoreId,
                    "pid": data_pid0,
                    "id": glFldId,
                    "name": date_text,
                    "link": data_link
                })
                data_pid1 = glFldId

                # Группы уровня 2
                sub_groups = get_list(topGroup, './/li[contains(@class,"header-nav-drop-down-column")]')
                for subGroup in sub_groups:
                    item_sub_link = get_first(subGroup, '*[@class="header-nav-drop-down-title"]/a')
                    if item_sub_link is not None:
                        data_link = item_sub_link.attrib['href']
                        date_text = item_sub_link.text_content().strip()
                        if skip_link(data_link):
                            continue

                        glFldId = glFldId + 1
                        db.insert_data_group({
                            "sid": glStoreId,
                            "pid": data_pid1,
                            "id": glFldId,
                            "name": date_text,
                            "link": data_link
                        })
                        data_pid2 = glFldId

                        # Группы уровня 3
                        sub_sub_groups = get_list(subGroup, 'ul/li[@class="header-nav-drop-down-list-item"]/a')
                        for subSubGroup in sub_sub_groups:
                            data_link = subSubGroup.attrib['href']
                            date_text = subSubGroup.text_content().strip()
                            if skip_link(data_link):
                                continue

                            glFldId = glFldId + 1
                            db.insert_data_group({
                                "sid": glStoreId,
                                "pid": data_pid2,
                                "id": glFldId,
                                "name": date_text,
                                "link": data_link
                            })
                            data_pid3 = glFldId

                            # многопоточность - 10 потоков
                            # t = threading.Thread(target=load_prods, args=(db, data_pid3, data_link))
                            # t.start()
                            # if threading.active_count() > 10:
                            #     t.join()

                            # монопоточность
                            load_prods(data_pid3, data_link)


db = priceview_db.PriceviewDB(glStoreId, datetime.datetime.utcnow().timestamp())
db.prepare_table_before_insert()

startTime = time.time()
load_catalog(storeURL)
print ("Время выполнения: {:.3f} сек".format(time.time() - startTime))

db.commit()

