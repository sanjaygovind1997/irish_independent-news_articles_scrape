import requests
from lxml import html
import re
import json
import os
from pathlib import Path
from nested_lookup import nested_lookup
from asyncio import create_task, gather, run
from unidecode import unidecode

from headers import listing_headers, artilce_page_headers, listing_graphql_headers
from regex_patterns import articles_list_regex, html_tags_pattern, json_regex
from xpaths import article_json_xpath, article_list_xpath

async def search_keyword(key_word, page_no, end_cursor=None):

    print(f"\nSearching for article URLs related to : {key_word}. Page Number : {page_no}\n")
    key_word_formatted = key_word.replace(' ', '+').lower()
    if page_no == 1:
        url = f'https://www.independent.ie/search?keyword={key_word_formatted}&daterange=all&datestart=&dateend='

        response = requests.get(url, headers=listing_headers)
        print(f"\n{key_word} : Page - {page_no} response statsus : {response.status_code}\n")
        parser = html.fromstring(response.text)
        articles_list_raw = parser.xpath(article_list_xpath)
        articles_list_raw = articles_list_raw[0] if articles_list_raw else None

        articles_list = re.search(articles_list_regex, articles_list_raw)
        articles_list = articles_list.group(1)
        articles_list = json.loads(articles_list)
    else:
        url = 'https://www.independent.ie/graphql-blue-mhie'
        params = {
            'variables': '{"brand":"independent.ie","count":50,"search":"' + key_word.lower() + '","publishedAfter":"","publishedBefore":"",'
            '"sections":[],"ordering":"MOST_RECENT","sourcesetCroppingInput":{"resizeMode":"CENTER_CROP","cropsMode":"LANDSCAPE","fallbackResizeMode":"SMART_CROP",'
            '"sizes":[{"key":"xsmall","width":120,"height":80},{"key":"small","width":160,"height":107},{"key":"smallMobile","width":240,"height":160},'
            '{"key":"medium","width":320,"height":213},{"key":"large","width":640,"height":427},{"key":"xlarge","width":960,"height":640},{"key":"xxlarge","width":1280,'
            '"height":853}]},"after":"' + end_cursor + '"}',
            'operationName': 'webv2_SearchArticlesConnection_indo_3_2',
            'persisted': 'true',
            'extensions': '{"persistedQuery":{"version":1,"sha256Hash":"43e500c22cefdeeb9dd4d386a63bcff60485f16d48e6419d65365f8e77e844b5"}}',
            }
        print(f"\nparams\n{params}")
        headers = listing_graphql_headers
        headers['referer'] = f'https://www.independent.ie/search?keyword={key_word_formatted}&daterange=all&datestart=&dateend='

        response = requests.get(url, params=params, headers=headers)
        print(f"\n{key_word} : Page - {page_no} response statsus : {response.status_code}\n")
        articles_list = response.json()

    print(url)
    data = nested_lookup('data', articles_list)

    total_count = data[0].get('search', {}).get('totalCount')
    print(f"\nTotals Articles listed on the website : {total_count}\n")
    page_info = data[0].get('search', {}).get('pageInfo', {})
    end_cursor, has_next_page = page_info.get('endCursor'), page_info.get('hasNextPage')
    articles = data[0].get('search').get('edges',[])

    article_urls = []
    for article in articles:
        article_url = 'https://www.independent.ie/' + article.get('node',{}).get('relativeUrl')
        article_urls.append(article_url)
    print(f"\nArticle URLs ({key_word}): \n", article_urls)

    print("\n Articles len : \n", len(article_urls))

    for url in article_urls:
        get_article_data(url, key_word, page_no)
        # break

    if has_next_page and page_no != 2:
        print(f"\nNext page exists! Getting next 50 URLs for {key_word} ...\n")
        page_no += 1
        await search_keyword(key_word, page_no, end_cursor)

def get_article_data(article_url, key_word, page_no):
    """
    Collects artcle title, author, publish date, content etc.
    Cleans the data and saves it in article_data.json file.
    """

    print(f"\nGathering articles for {key_word} {page_no}\n")

    response = requests.get(article_url, headers=artilce_page_headers)
    parser = html.fromstring(response.text)
    article_json_raw = parser.xpath(article_json_xpath)
    article_json_raw = article_json_raw[0] if article_json_raw else None
    article_json_raw = re.search(json_regex, article_json_raw).group(1)
    article_json = json.loads(article_json_raw)

    article = nested_lookup('article', article_json)[0] if nested_lookup('article', article_json) else {}

    title = unidecode(article.get("title"))
    url = article.get("url", response.url)
    author = unidecode(article.get("author"))
    authors = article.get("authors")
    published_date = article.get("publishedAt")
    type_ = article.get("type")

    article_body = article.get('body', [])
    article_intro = article.get("intro", [])
    article_body = article_intro + article_body
    paragraph_elems = [tag_data for tag_data in article_body if 'p' in tag_data.keys()]
    paragraph = clean_paragraphs(paragraph_elems)

    final_data = {
        "title": title,
        "article_url": url,
        "author": author,
        "authors": authors,
        "date_published": published_date,
        "type_of_content": type_,
        "article": paragraph
    }
    write_to_file(final_data)

def clean_paragraphs(paragraph_elems):
    """
    Extracts article's paragraph texts(contained in <p> tags), strips any html tags present in it.
    """
    paragraphs = [re.sub(html_tags_pattern, '', elem['p']) for elem in paragraph_elems if elem.get('p')]
    combined_paragraphs = ' '.join(paragraphs)
    return unidecode(combined_paragraphs)

def write_to_file(data):
    """
    Saves the data of an article to a file in JSON fromat.
    File is created if not already present, updates with new data if file is present.
    """
    path_to_this_folder = os.path.dirname(Path(__file__).resolve())
    file_path = os.path.join(path_to_this_folder, 'article_data.json')
    file_exists = os.path.exists(file_path)

    if file_exists:
        with open(file_path, 'r') as file:
            file_data = json.load(file)
            file_data.append(data)

        with open(file_path, 'w') as file:
            json.dump(file_data, file)
    else:
        print("\nOutput file doesn't exist. Creating . . .\n")
        with open(file_path, 'w') as file:
            articles_list = [data]
            json.dump(articles_list, file)


async def main():
    """
    Add the necessary key words for searching to the key_words list.
    Function will search for the articles and extract data
    """

    key_words = ["Substance Abuse", "murder"]

    tasks = [ create_task(search_keyword(key_word, 1)) for key_word in key_words]
    await gather(*tasks)


run(main())
