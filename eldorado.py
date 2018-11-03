import lxml.html as xhtml
import urllib.request
import urllib.error
import urllib.parse
import uuid
import datetime
import time
import priceview_db


# базовый URL сайта
storeURL = 'https://www.eldorado.ru'
# идентификатор магазина
glStoreId = 2
glFldId = 0


def get_http_opener():
    opener = urllib.request.build_opener(urllib.request.HTTPRedirectHandler)
    opener.addheaders.append(("Cookie", "iRegionSectionId=11365"))  # Киров
    opener.addheaders.append(("User-Agent", "" + str(uuid.uuid4()) + 'Mozilla'))
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
    return byte_text


def skip_link(str_link):
    if str_link.find('/prm/') != -1:
        return True
    elif str_link.find('/promo/') != -1:
        return True
    elif str_link.find('/search/') != -1:
        return True
    elif str_link == '/cat/1482093/':  # все телевизоры
        return True
    else:
        return False


def load_prods(pid, link):
    global db
    global glFldId

    page_url = urllib.parse.urljoin(storeURL, link) + '?list_num=36'
    tryCount = 3

    # цикл чтения неопреденного числа страниц
    while True:

        print(page_url)

        # чтение страници и преобразовнаие в xml
        try:
            opener = get_http_opener()
            response = opener.open(page_url, None, 20)
        except urllib.error.HTTPError:
            if tryCount > 0:
                tryCount = tryCount - 1
                print('осталось попыток {0}'.format(tryCount))
                continue
            else:
                break

        html_text = response.read()
        page = xhtml.fromstring(correct_text(html_text))

        # прочитаем все товары на странице
        # а если есть следующая страница, то перейдем к чтении ее
        prods_array = []
        joins_array = []

        # выборка запросом списка продуктов
        prods = get_list(page, '//div[contains(@class,"goodsList")]/div[contains(@class,"item")]')
        for prod in prods:

            prod_link = get_first(prod, './/div[@class="itemTitle"]/a')
            if prod_link is None:
                continue

            price_link = get_first(prod, './/div[@class="priceContainer"]//a[contains(@class,"cartButton")]')
            if price_link is None:
                continue

            data_link = prod_link.attrib['href']
            data_name = prod_link.text_content().strip()
            data_price = price_link.attrib['data-price']
            data_id = price_link.attrib['data-xid']
            data_category = ''
            data_vendor = ''

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

        next_page_link = get_first(page, '//div[@class="pages"]/a[@class="page pageActive"]/following-sibling::a')
        if next_page_link is not None:
            # есть следующая страница, продолжаем цикл чтения страниц
            page_url = urllib.parse.urljoin(storeURL, next_page_link.attrib['href'])
            continue  # переход к чтению следующей страницы

        break  # while True


def load_catalog(catalog_link):
    global db
    global glFldId

    print(catalog_link)
    # чтение страници и преобразовнаие в xml
    opener = get_http_opener()
    page = xhtml.fromstring(opener.open(catalog_link).read())
    data_pid0 = 0

    # Группы уровня 1
    top_groups = get_list(page, '//ul[@class="main-menu"]/li[contains(@class,"headerCatalogItem")]')
    for topGroup in top_groups:

        # группа
        item_link = get_first(topGroup, 'noindex/a[contains(@class,"headerCatalogItemLink") and not(contains(@class,"promo"))]')
        if item_link is None:
            continue

        data_link = item_link.attrib['href']
        if skip_link(data_link):
            continue

        item_text = get_first(item_link, 'span[contains(@class,"text")]')
        if item_text is None:
            continue

        date_text = item_text.text_content().strip()

        glFldId = glFldId + 1
        db.insert_data_group({
            "sid": glStoreId,
            "pid": data_pid0,
            "id": glFldId,
            "name": date_text,
            "link": data_link
        })
        data_pid1 = glFldId
        data_pid2 = data_pid1

        # Группы уровня 2 и 3
        sub_groups = get_list(topGroup, './/li/a[contains(@class,"headerCatalogSubItem")]')
        for subGroup in sub_groups:
            data_link = subGroup.attrib['href']
            date_text = subGroup.text_content().strip()
            if skip_link(data_link):
                continue

            glFldId = glFldId + 1

            if subGroup.attrib['class'].find('headerCatalogSubSection') != -1:
                # уровень 2
                data_pid = data_pid1
                data_pid2 = glFldId
            else:
                # уровень 3
                data_pid = data_pid2

            db.insert_data_group({
                "sid": glStoreId,
                "pid": data_pid,
                "id": glFldId,
                "name": date_text,
                "link": data_link
            })

            load_prods(glFldId, data_link)


db = priceview_db.PriceviewDB(glStoreId, datetime.datetime.utcnow().timestamp())
db.prepare_table_before_insert()

startTime = time.time()
load_catalog(storeURL)
print ("Время выполнения: {:.3f} сек".format(time.time() - startTime))

db.commit()

