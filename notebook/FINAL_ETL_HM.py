#!/usr/bin/env python
# coding: utf-8

# In[1]:


# IMPORTS

import requests
import pandas as pd
from datetime import datetime
from bs4 import BeautifulSoup
import numpy as np
import seaborn as sns
import re
import os
import sqlite3
from sqlalchemy import create_engine
import sqlalchemy as sa
import logging

#  DATA COLLECTION

def data_collection (url, headers):

    # request to URL
    page_base = requests.get( url, headers=headers )
    
    # Beautifoul soup object
    soup_base = BeautifulSoup(page_base.text, 'html.parser')

    # PAGE WITH ALL ITENS SHOWN

    total_item = soup_base.find_all( 'h2', class_='load-more-heading' )[0].get('data-total')


    url_showroom = url + '?page-size=' + total_item
    url_showroom

    headers_showroom = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36'}
    page_showroom = requests.get( url_showroom, headers=headers_showroom )

    soup_showroom = BeautifulSoup(page_showroom.text, 'html.parser')

    #================================== PRODUCT DATA ================================================
    products_base=soup_showroom.find( 'ul', class_='products-listing small')
    product_list_base = products_base.find_all( 'article', class_='hm-product-item')

    # product id

    product_id_base = [p.get( 'data-articlecode' ) for p in product_list_base]

    # product category
    product_category_base = [p.get( 'data-category' ) for p in product_list_base]

    # product name
    product_list_base = products_base.find_all( 'a', class_='link' )
    product_name_base = [p.get_text() for p in product_list_base]

    # price
    product_list_base = products_base.find_all( 'span', class_='price regular' )
    product_price_base = [p.get_text() for p in product_list_base]


    # JOIN
    data=pd.DataFrame([product_id_base, product_category_base, product_name_base, product_price_base]).T
    data.columns=['product_id', 'product_category', 'product_name', 'product_price']

    # ALL PRODUCTS LINK
    prod_link01=soup_showroom.find_all('div', 'image-container')
    prod_link02=[p.find('a') for p in prod_link01]
    prod_link=[p.get('href') for p in prod_link02]
    
    return data


# DATA COLLETION BY PRODUCT

def data_collection_by_product( data, headers ):

    # empty dataframe
    df_compositions = pd.DataFrame()

    # unique columns for all products
    aux = []

    df_pattern = pd.DataFrame(columns=['Art. No.', 'Composition', 'Fit', 'Product safety',
                                       'Size', 'More sustainable materials'])
    for i in range(len(data)):
        # API request
        url = 'https://www2.hm.com/en_us/productpage.' + data.loc[i, 'product_id'] + '.html'
        logger.debug('Prouct: %s', url)
        page = requests.get(url, headers=headers)

        # Beautiful Soup object
        soup = BeautifulSoup(page.text, 'html.parser')

        # ==================== color name ====================================
        product_list = soup.find_all('a', class_='filter-option miniature active') + soup.find_all('a', class_='filter-option miniature')
        color_name = [p.get('data-color') for p in product_list]

        # product id
        product_id = [p.get('data-articlecode') for p in product_list]

        df_color = pd.DataFrame([product_id, color_name]).T
        df_color.columns = ['product_id', 'color_name']

        for j in range(len(df_color)):
            # API request
            url = 'https://www2.hm.com/en_us/productpage.' + df_color.loc[j, 'product_id'] + '.html'
            logger.debug('Color: %s', url)
            
            page = requests.get(url, headers=headers)

            # Beautiful Soup object
            soup = BeautifulSoup(page.text, 'html.parser')

            # ===================== Product Name =========================
            product_name = soup.find_all('h1', class_='primary product-item-headline')

            if len(product_name) > 0:
                product_name = product_name[0].get_text()

                # ===================== Product Price =========================
                product_price = soup.find_all('div', class_='primary-row product-item-price')
                product_price = re.findall(r'\d+\.?\d+', product_price[0].get_text())[0]

                # ==================== composition ====================================
                product_composition_list = soup.find_all('div', class_='pdp-description-list-item')
                product_composition = [list(filter(None, p.get_text().split('\n'))) for p in product_composition_list]

                if len(product_composition) > 0:
                    # rename dataframe
                    df_composition = pd.DataFrame(product_composition).T

                    df_composition.columns = df_composition.iloc[0]

                    # delete first row
                    df_composition = df_composition.iloc[1:].fillna(method='ffill')

                    # remove pocket lining, shell and lining
                    df_composition['Composition'] = df_composition['Composition'].replace('Pocket lining: ', '', regex=True)
                    df_composition['Composition'] = df_composition['Composition'].replace('Shell: ', '', regex=True)
                    df_composition['Composition'] = df_composition['Composition'].replace('Lining: ', '', regex=True)

                    # garantee the same number of columns
                    df_composition = pd.concat([df_pattern, df_composition], axis=0)

                    # rename columns
                    df_composition.columns = ['product_id', 'composition', 'fit', 'product_safety', 'size', 'sustainable']
                    df_composition['product_name'] = product_name
                    df_composition['product_price'] = product_price

                    # keep new columns if it shows up
                    aux = aux + df_composition.columns.tolist()

                    # merge data color + composition
                    df_composition = pd.merge(df_composition, df_color, how='left', on='product_id')

                    # all products
                    df_compositions = pd.concat([df_compositions, df_composition], axis=0)

    # Join Showroom data + details
    df_compositions['style_id'] = df_compositions['product_id'].apply(lambda x: x[:-3])
    df_compositions['color_id'] = df_compositions['product_id'].apply(lambda x: x[-3:])

    # scrapy datetime
    df_compositions['scrapy_datetime'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    return df_compositions

# DATA CLEANING

def data_cleaning(df_compositions):
    
    df_data=df_compositions
    df_data.rename(columns={'scrapy_datetime_base': 'scrapy_datetime', 'Fit': 'fit', 
                         'Composition': 'composition', 'Size': 'size', 'Prouct safety': 'product_safety'}, inplace=True)

    # product_id
    df_data=df_data.dropna(subset=['product_id'])
    df_data['product_id']=df_data['product_id'].astype('int64')

    # product_name  
    df_data['product_name']=df_data['product_name'].apply(lambda x: x.replace('__', ' ').lower().strip()) 
    df_data['product_name']=df_data['product_name'].apply(lambda x: x.replace(' ', '_').lower().strip()) 

    # product_price  
    # df_data['product_price']=df_data['product_price'].apply(lambda x: x.replace('$', ' ')).astype(float)

    # scrapy_datetime 
    df_data['scrapy_datetime']=pd.to_datetime(df_data['scrapy_datetime'], format='%Y-%m-%d %H:%M:%S')

    # style_id              
    df_data['style_id']=df_data['style_id'].astype('int64')

    # color_id              
    df_data['color_id']=df_data['color_id'].astype('int64')

    # color name
    df_data['color_name'] = df_data['color_name'].apply( lambda x: x.replace( ' ', '_' ).replace( '/', '_' ).lower() if pd.notnull( x ) else x )

    # fit
    df_data['fit'] = df_data['fit'].apply( lambda x: x.replace( ' ', '_' ).lower() if pd.notnull( x ) else x )

    # Size number
    df_data['size_number']=df_data['size'].apply(lambda x: re.search('\d{3}cm',x).group(0) if pd.notnull(x) else x)
    df_data['size_number']=df_data['size_number'].apply(lambda x: re.search('\d+',x).group(0) if pd.notnull(x) else x)

    # Size model
    df_data['size_model'] = df_data['size'].str.extract( '(\d+/\\d+)' )

    # composition
    df_data =df_data[~df_data['composition'].str.contains('Pocket lining:', na=False)]
    df_data =df_data[~df_data['composition'].str.contains('Lining:', na=False)]
    df_data =df_data[~df_data['composition'].str.contains('Shell:', na=False)]
    df_data =df_data[~df_data['composition'].str.contains('Pocket:', na=False)]

    # drop duplicates
    df_data= df_data.drop_duplicates(subset=['product_id', 'product_name', 'product_price',
                                       'scrapy_datetime', 'style_id', 'color_id', 'color_name', 'fit'], keep='last')
    # reset index
    df_data= df_data.reset_index(drop=True)

    # break composition by comma
    df1= df_data['composition'].str.split(',',expand=True)

    # cotton | polyester | elastano | elastarell
    df_ref=pd.DataFrame(index=np.arange(len(df_data)),columns=['cotton' , 'polyester' , 'elastane' , 'elasterell'])

    # cotton
    df_cotton = df1[0]
    df_cotton.name='cotton'

    df_ref = pd.concat([df_ref, df_cotton], axis=1)
    df_ref = df_ref.iloc[: , ~df_ref.columns.duplicated(keep='last')]
    df_ref['cotton']=df_ref['cotton'].fillna('Cotton 0%')

    # polyester
    df_polyester=df1.loc[df1[1].str.contains('Polyester' , na=True), 1]
    df_polyester.name='polyester'

    df_ref = pd.concat([df_ref, df_polyester], axis=1)
    df_ref = df_ref.iloc[: , ~df_ref.columns.duplicated(keep='last')]
    df_ref['polyester']=df_ref['polyester'].fillna('Polyester 0%')

    # elastano
    df_elastane=df1.loc[df1[1].str.contains('Elastane', na=True), 1]
    df_elastane.name='elastane'

    # combine elastane from both columns 1 and 2
    df_elastane=df_elastane.combine_first(df1[2])

    df_ref = pd.concat([df_ref, df_elastane], axis=1)
    df_ref = df_ref.iloc[: , ~df_ref.columns.duplicated(keep='last')]
    df_ref['elastane']=df_ref['elastane'].fillna('Elastane 0%')

    # elastarell
    df_elasterell=df1.loc[df1[1].str.contains('Elasterell' , na=True), 1]
    df_elasterell.name='elasterell'

    df_ref = pd.concat([df_ref, df_elasterell], axis=1)
    df_ref = df_ref.iloc[: , ~df_ref.columns.duplicated(keep='last')]
    df_ref['elasterell']=df_ref['elasterell'].fillna('Elasterell 0%')

    # final join
    df_data=pd.concat([df_data, df_ref], axis=1)
    df_data=df_data.dropna(how='all').reset_index(drop=True)
    df_data = df_data.iloc[: , ~df_data.columns.duplicated(keep='last')]

    # format composition df_data
    df_data['cotton']    =df_data['cotton']    .apply( lambda x: int(re.search('\d+', x).group(0)) / 100 if pd.notnull(x) else x)
    df_data['polyester'] =df_data['polyester'] .apply( lambda x: int(re.search('\d+', x).group(0)) / 100 if pd.notnull(x) else x)
    df_data['elastane']  =df_data['elastane']  .apply( lambda x: int(re.search('\d+', x).group(0)) / 100 if pd.notnull(x) else x)
    df_data['elasterell']=df_data['elasterell'].apply( lambda x: int(re.search('\d+', x).group(0)) / 100 if pd.notnull(x) else x)

    df_data['product_id']=df_data['product_id'].astype('int64')
    df_data['style_id']  =df_data['style_id'].astype('int64')
    df_data['color_id']  =df_data['color_id'].astype('int64')

    # drop columns
    df_data = df_data.drop( columns=['size', 'product_safety', 'composition'], axis=1 )

    # drop duplicates
    df_data = df_data.drop_duplicates()
#     df_data=df_data.drop(columns=['Unnamed: 0'])
    
    return df_data


# DATA INSERT

def data_insert(df_data):

    data_insert = df_data[[
        'product_id',
        'style_id',
        'color_id',
        'product_name',
        'color_name',
        'fit',
        'product_price',
        'size_number',
        'size_model',
        'cotton',
        'polyester',
        'elastane',
        'elasterell',
        'sustainable',
        'scrapy_datetime'
        ]]


    # create table
    conn=create_engine('sqlite:///database_hm.sqlite', echo=False)

    # data insert
    data_insert.to_sql('vitrine', con=conn, if_exists='append', index=False)
    
    return None


if __name__ == "__main__":
    
    path = 'C:/Users/djalmaluiz/DS/starjeans/'
    if not os.path.exists( path + 'Logs' ):
        os.makedirs( path + 'Logs' )

    logging.basicConfig(
        filename='C:/Users/djalmaluiz/DS/starjeans/Logs/webscraping_hm_etl.log',
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
        datefmt= '%Y-%m-%d %H:%M:%S:'
        )

    logger = logging.getLogger('webscraping_hm')



    # parameters
    url = 'https://www2.hm.com/en_us/men/products/jeans.html'
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36'}
    
    
    # data colletion
    data=data_collection (url, headers)
    logger.info('data collectin done')    
    
    # data colletion by product
    df_compositions = data_collection_by_product(data, headers)
    logger.info('data collect by product done')
    
    # data cleaning
    data_product_cleaned =  data_cleaning(df_compositions)
    logger.info('data cleaning done')
    
    # data insertion
    data_insert(data_product_cleaned)
    logger.info('data insertion done')

