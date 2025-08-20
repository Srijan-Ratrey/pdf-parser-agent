import pandas as pd
import pdfplumber

def parse(pdf_path):
    try:
        with pdfplumber.open(pdf_path) as pdf:
            all_data = []
            for page in pdf.pages:
                table = page.extract_table()
                if table:
                    all_data.extend(table[1:])

            df = pd.DataFrame(all_data, columns=table[0])
            df['Debit Amt'] = pd.to_numeric(df['Debit Amt'], errors='coerce')
            df['Credit Amt'] = pd.to_numeric(df['Credit Amt'], errors='coerce')
            df['Balance'] = pd.to_numeric(df['Balance'], errors='coerce')

            if len(df) > 100:
                df = df[:100]
            elif len(df) < 100:
                df = pd.concat([df, pd.DataFrame(columns=df.columns, index=range(len(df),100))])

            return df
    except FileNotFoundError:
        print(f"Error: PDF file not found at {pdf_path}")
        return pd.DataFrame(columns=['Date', 'Description', 'Debit Amt', 'Credit Amt', 'Balance'], index=range(100))
    except Exception as e:
        print(f"An error occurred: {e}")
        return pd.DataFrame(columns=['Date', 'Description', 'Debit Amt', 'Credit Amt', 'Balance'], index=range(100))