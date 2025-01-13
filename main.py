import pandas as pd
import re
import traceback

file = 'uncleaned_data.csv'
df = pd.read_csv(file) 
df.fillna('', inplace=True)
zip_code_pattern = r'^\d{5}(-\d{4})?$|([A-Z]\d[A-Z] \d[A-Z]\d|[A-Z]\d[A-Z]\d[A-Z]\d|[A-Z]\d[A-Z] \d[A-Z]\d|[A-Z]\d[A-Z] [A-Z]\d)'

def data_summary(df):
    print('INFO:')
    print(df.info())
    print("---------------------")
    print('SUMMARY:')
    print(df.describe())
    print("---------------------")
    
def validate_data(df):
    
    not_null_data = df[df[['PURCHASE ORDER NUMBER', 'REQUISITION NUMBER', 'INPUT DATE', 'TOTAL AMOUNT', 
                           'DEPARTMENT NUMBER', 'COST CENTER', 'INPUT BY', 'PO TYPE CODE', 'PO STATUS CODE', 
                           'VENDOR NUMBER', 'TOTAL ITEMS', 'UNIQUE ID']].isnull().any(axis=1)]
    
    df['INPUT DATE'] = df['INPUT DATE'].fillna('').astype(str)
    invalid_dates = df[~df['INPUT DATE'].astype(str).str.match(r'^\d{1,2}/\d{1,2}/\d{2}$')]
   
   #convert all columns that should be number types into numeric values and find those that are not
    numeric_columns = ['TOTAL AMOUNT', 'PO STATUS CODE', 'VOUCHED AMOUNT', 'VENDOR NUMBER', 
                        'VENDOR CONTACT EXTENSION', 'TOTAL ITEMS', 
                       'PO BALANCE', 'ITEM NUMBER', 'ITEM QUANTITY ORDERED', 'ITEM UNIT COST', 
                       'ITEM TOTAL COST']
    invalid_numeric = pd.DataFrame()
    for col in numeric_columns:
        df[col] = pd.to_numeric(df[col], errors='coerce')
        if df[col].isnull().any():
            print(f"Invalid values in column {col}")
            invalid_numeric = pd.concat([invalid_numeric, df[df[col].isnull()]])
    
    df['VENDOR ZIP'] = df['VENDOR ZIP'].fillna('').astype(str)
    invalid_zip = df[~df['VENDOR ZIP'].astype(str).str.match(r'^\d{5}(-\d{4})?$')]
                                                 
    log = {
        'not_null_data': not_null_data,
        'invalid_dates': invalid_dates,
        'invalid_numeric': invalid_numeric,
        'invalid_zip': invalid_zip
    }

    print(log)

#function to handle invalid zip codes
def handle_zip_code(zip_code):
    # check zip codes
    if re.match(zip_code_pattern, zip_code):
        return zip_code
    elif len(zip_code) == 4:
        return '0' + zip_code  # Prepend 0 for 4-digit zip codes
    else:
        return ''  # Replace with empty string if less than 4 digits


def cleanse_data(df):
    #remove leading and trailing whitespace in all columns
    for col in df.columns:
        df[col] = df[col].astype(str).str.strip()
    
    df.loc[(df['REQUISITION NUMBER'].isna()), 'REQUISITION NUMBER'] = 'UNKNOWN'
    df.loc[(df['PO CATEGORY CODE'].isna()), 'PO CATEGORY CODE'] = 'UNKNOWN'

    
    #-------NUMERIC----------
    numeric_columns = ['PO STATUS CODE', 'VENDOR NUMBER', 'VENDOR CONTACT EXTENSION', 'TOTAL ITEMS', 'ITEM NUMBER', 'ITEM QUANTITY ORDERED']
    for col in numeric_columns:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    text_columns = ['RECORD TYPE', 'PURCHASE ORDER NUMBER', 'REQUISITION NUMBER', 'DEPARTMENT NUMBER', 'DEPARTMENT NAME', 'COST CENTER', 'COST CENTER NAME', 'INPUT BY', 'PURCHASING AGENT', 'PO TYPE CODE', 'PO TYPE DESCRIPTION', 'PO CATEGORY CODE', 'PO CATEGORY DESCRIPTION', 'PO STATUS DESCRIPTION', 'VENDOR NAME 1', 'VENDOR NAME 2', 'VENDOR ADDRESS 1', 'VENDOR ADDRESS 2', 'VENDOR CITY', 'VENDOR STATE', 'VENDOR ZIP', 'VENDOR CONTACT NAME', 'VENDOR CONTACT TITLE', 'VENDOR MINORITY CODE', 'VENDOR MINORITY DESCRIPTION', 'ITEM DESCRIPTION', 'ITEM UNIT OF MEASURE', 'ITEM UNIT OF MEASURE DESCRIPTION', 'UNIQUE ID']
    for col in text_columns:
        df[col] = df[col].fillna('').astype(str)

    #---------INPUT DATE----------
    df['INPUT DATE'] = pd.to_datetime(df['INPUT DATE'], errors='coerce').dt.strftime('%m/%d/%Y')

    #--------MONEY-----------
    money_columns = ['TOTAL AMOUNT', 'VOUCHED AMOUNT', 'PO BALANCE', 'ITEM UNIT COST', 'ITEM TOTAL COST']
    for col in money_columns:
        df[col] = pd.to_numeric(df[col], errors='coerce').round(2)

    #---------PO TYPE CODE and RECORD TYPE-------------
    record_types = ['H', 'D']
    df['RECORD TYPE'] = df['RECORD TYPE'].where(df['RECORD TYPE'].isin(record_types), '')
    po_type_codes = ['G', 'S', 'B']
    df['PO TYPE CODE'] = df['PO TYPE CODE'].where(df['PO TYPE CODE'].isin(po_type_codes), '')

    #---------PHONE NUMBER-----------
    #df['VENDOR CONTACT PHONE'] = df['VENDOR CONTACT PHONE'].astype(str).where(df['VENDOR CONTACT PHONE'].astype(str).str.match(r'^\d{10}$'), '')
    
    # -------VENDOR DATA-----------
    # create COUNTRY column. change to 'CANADA' if state column has 'CANADA', ',' or 'CD', else 'UNITED STATES'
    df['VENDOR COUNTRY'] = df['VENDOR STATE'].apply(lambda x: 'CANADA' if ',' in x or x == 'CD' else 'UNITED STATES')
    # change country column to CANADA based on city column value of ','
    df.loc[df['VENDOR CITY'] == 'CANADA', 'VENDOR COUNTRY'] = 'CANADA'

    #regex for canadian post codes, provinces, and cities
    postal_code_pattern = r'(\b\d{5}(-\d{4})?\b|[A-Z]\d[A-Z]\d[A-Z]\d|[A-Z]\d[A-Z]\s?\d[A-Z]\d|[A-Z]\d[A-Z]\s?[A-Z]\d|[A-Z]\d{4}|[A-Z]\d[A-Z]\s?\d[A-Z]\d|[A-Z]\d[A-Z]{2}\d{2})'
    
    province_pattern = r'\b(ONTARIO|QUEBEC|ON|ONT|BC|QC)\b'
    city_pattern = r'\b(MONTREAL|PICKERING|KANLOOPS)\b'

    for index, row in df.iterrows():
        address2 = row['VENDOR ADDRESS 2']
        city = row['VENDOR CITY']
    
        # find canadian postal codes in VENDOR ADDRESS 2
        match = re.search(postal_code_pattern, address2)
        if match:
            postal_code = match.group(1)
            # strip postal code from address
            address_without_postal = re.sub(postal_code_pattern, '', address2).strip()
            # update rows
            df.at[index, 'VENDOR ADDRESS 2'] = address_without_postal
            df.at[index, 'VENDOR ZIP'] = postal_code

        match2 = re.search(postal_code_pattern, city)
        if match2:
            postal_code = match2.group(1)
            #strip postal code from city
            city_without_postal = re.sub(postal_code_pattern, '', city).strip()
            #update city
            df.at[index, 'VENDOR CITY'] = city_without_postal
            #remove 'CANADA' from updated city column
            city_without_country = re.sub('CANADA', '', df.at[index, 'VENDOR CITY']).strip()
            df.at[index, 'VENDOR CITY'] = city_without_country
            df.at[index, 'VENDOR ZIP'] = postal_code

        match3 = re.search(province_pattern, df.at[index, 'VENDOR CITY'])
        if match3:
            # strip province from city column
            province_name = match3.group(1)
            city_without_province = re.sub(province_pattern, '', df.at[index, 'VENDOR CITY']).strip()
            df.at[index, 'VENDOR CITY'] = city_without_province
            df.at[index, 'VENDOR STATE'] = province_name
        
        match4 = re.search(province_pattern, df.at[index, 'VENDOR ADDRESS 2'])
        if match4:
            # strip province from address 2
            province_title = match4.group(1)
            address_without_province = re.sub(province_pattern, '', df.at[index, 'VENDOR ADDRESS 2']).strip()
            df.at[index, 'VENDOR ADDRESS 2'] = address_without_province
            df.at[index, 'VENDOR STATE'] = province_title

        match5 = re.search(city_pattern, df.at[index,'VENDOR ADDRESS 2'])
        if match5:
            city_title = match5.group(1)
            address_without_city = re.sub(city_pattern, '', df.at[index, 'VENDOR ADDRESS 2']).strip()
            df.at[index, 'VENDOR ADDRESS 2'] = address_without_city
            df.at[index, 'VENDOR CITY'] = city_title
            
    df['VENDOR STATE'] = df['VENDOR STATE'].replace({
    'ONTARIO': 'ON',
    'ONT': 'ON',
    'QUEBEC': 'QB'
    })
    df['VENDOR ZIP'] = df['VENDOR ZIP'].str.replace(' ', '', regex=False)
    df['VENDOR ZIP'] = df['VENDOR ZIP'].apply(handle_zip_code)

    #drop duplicate unique ids 
    df.drop_duplicates(subset=['UNIQUE ID'], inplace=True)

    # remove all commas to prevent access from inputting values in incorrect fields
    df['ITEM DESCRIPTION'] = df['ITEM DESCRIPTION'].str.replace(',', '', regex=False)

    return df

def main():
    try:
        #data_summary(df)
        validate_data(df)
        cleaned_df = cleanse_data(df)

        if cleaned_df.empty:
            print("Cleaned data is empty.")
        else:
            cleaned_df.to_csv('clean_data.csv', index=False)
            print("Cleaned data saved to 'clean_data.csv'.")
    except Exception as e:
        tb = traceback.format_exc()
        print(f"An error occured: {e}")
        print(tb)

if __name__ == '__main__':
    main()
