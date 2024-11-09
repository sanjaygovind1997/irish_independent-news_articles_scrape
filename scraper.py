import requests
from lxml import html
import re
import json
import os
from pathlib import Path
from nested_lookup import nested_lookup

from headers import listing_headers, artilce_page_headers
from regex import articles_list_regex, html_tags_pattern, json_regex
from xpaths import article_json_xpath, article_list_xpath


def get_article_data(article_url):
    """
    Collects artcle title, author, publish date, content etc.
    Cleans the data and saves it in article_data.json file.
    """

    response = requests.get(article_url, headers=artilce_page_headers)
    parser = html.fromstring(response.text)
    article_json_raw = parser.xpath(article_json_xpath)
    article_json_raw = article_json_raw[0] if article_json_raw else None
    article_json_raw = re.search(json_regex, article_json_raw).group(1)
    article_json = json.loads(article_json_raw)

    article = nested_lookup('article', article_json)[0] if nested_lookup('article', article_json) else {}

    title = article.get("title")
    url = article.get("url", response.url)
    author = article.get("author")
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
    return ' '.join(paragraphs)

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


def main():
    """
    Add the necessary key words for searching to the key_words list.
    Function will search for the articles and extract data
    """

    key_words = ["Substance Abuse"]

    for key_word in key_words:
        key_word = key_word.replace(' ', '+').lower()
        url = f'https://www.independent.ie/search?keyword={key_word}&daterange=all&datestart=&dateend='

        response = requests.get(url, headers=listing_headers)
        parser = html.fromstring(response.text)
        articles_list_raw = parser.xpath(article_list_xpath)
        articles_list_raw = articles_list_raw[0] if articles_list_raw else None

        articles_list = re.search(articles_list_regex, articles_list_raw)
        articles_list = articles_list.group(1)
        articles_list = json.loads(articles_list)

        data = nested_lookup('data', articles_list)

        total_count = data[0].get('search', {}).get('totalCount')
        page_info = data[0].get('search', {}).get('pageInfo', {})
        end_cursor, has_next_page = page_info.get('endCursor'), page_info.get('hasNextPage')
        articles = data[0].get('search').get('edges',[])

        article_urls = []
        for article in articles:
            article_url = 'https://www.independent.ie/' + article.get('node',{}).get('relativeUrl')
            article_urls.append(article_url)
        print("Article URLs : ", article_urls)

        for url in article_urls:
            get_article_data(url)
            # break

main()
