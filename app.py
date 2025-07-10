import os
# set environment variables to fix problem with easyocr
# OMP: Error #15: Initializing libiomp5md.dll, but found libiomp5md.dll already initialized.
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
from copy import deepcopy
import numpy as np
import pandas as pd
import streamlit as st

from utils.process_mission_statement import generate_mission_statement
from utils.utils import *


# if not "OCR_READER" in globals() or not "OCR_READER" in locals():
#     OCR_READER = easyocr.Reader(['en', 'es', 'fr', 'it', 'de'], gpu=False)


def update_summary_table():
    # add sum of expenses to summary table
    df = st.session_state.expenses
    if len(st.session_state.expenses.columns) == 5:
        st.session_state.expense_summary.at[0, "Amount"] = df[df["Category"] == "Accommodation"]["Paid amount"].sum()
        st.session_state.expense_summary.at[1, "Amount"] = df[(df["Category"] == "Flights") |
                                                            (df["Category"] == "Train") |
                                                            (df["Category"] == "Bus") |
                                                            (df["Category"] == "Metro") |
                                                            (df["Category"] == "Taxi") |
                                                            (df["Category"] == "Rental car") |
                                                            (df["Category"] == "Own car") |
                                                            (df["Category"] == "Additional travel expenses")]["Paid amount"].sum()
        st.session_state.expense_summary.at[2, "Amount"] = df[df["Category"] == "Meals"]["Paid amount"].sum()
    elif len(st.session_state.expenses.columns) == 7:
        st.session_state.expense_summary.at[0, "Amount"] = df[df["Category"] == "Accommodation"]["Paid amount (EUR)"].sum()
        st.session_state.expense_summary.at[1, "Amount"] = df[(df["Category"] == "Flights") |
                                                            (df["Category"] == "Train") |
                                                            (df["Category"] == "Bus") |
                                                            (df["Category"] == "Metro") |
                                                            (df["Category"] == "Taxi") |
                                                            (df["Category"] == "Rental car") |
                                                            (df["Category"] == "Own car") |
                                                            (df["Category"] == "Additional travel expenses")]["Paid amount (EUR)"].sum()
        st.session_state.expense_summary.at[2, "Amount"] = df[df["Category"] == "Meals"]["Paid amount (EUR)"].sum()
    st.session_state.expense_summary.at[3, "Amount"] = st.session_state.expense_summary.loc[:2]["Amount"].sum()


def add_expense(category: str, description: str, amount: float, currency: str, attachment: io.BytesIO | dict, exchange_rate: float = 1.0):
    # Check expense parameters provided
    if amount == 0.0:
        zero_expense_error(currency=currency)
        return
    if attachment is None:
        attachment_error()
        return
    if currency != "EUR" and exchange_rate is None:
        exchange_rate_error()
        return
    if isinstance(attachment, io.BytesIO):
        if attachment.type == "application/pdf":
            pass
        elif attachment.type not in ["image/png", "image/jpeg", "image/tiff"]:
            image_format_error()
            return
    if category == "Flights":
        if attachment["invoice"] is None or attachment["boarding passes"] is None:
            flight_error()
            return
        else:
            boarding_passes = attachment["boarding passes"]
            attachment = attachment["invoice"]
            attachment_names = ", ".join([attachment.name] + [file.name for file in boarding_passes])
    else:
        attachment_names = attachment.name
    
    
    # Process attachments (all sorts of)
    # with st.spinner("Processing attachments... please wait..."):
    if category != "Own car":
        try:
            a_ok, a_new, a_size, a_conf = check_attachment(category=category, amount=amount, attachment=attachment)  #, reader=OCR_READER)
        except Exception as err:
            check_attachment_error(err)
            return
        else:
            if not any(a_ok):
                attachment_warning(amount=amount, currency=currency, confidence=np.average(a_conf))
    else:
        a_new = [attachment]
        a_size = [(16.25, None)]
        idx = st.session_state.expenses.shape[0]
        st.session_state.kilometers_own_car.update({idx: amount})
        if len(st.session_state.expenses.columns) == 5:
            amount *= 0.28
            amount = round(amount, 2)
            currency = "EUR"
            exchange_rate = 1.0
        else:
            currency = "km"
            exchange_rate = 0.28
    if category == "Flights":
        boarding_passes, boarding_passes_sizes = check_boarding_passes(boarding_passes)
        a_new += boarding_passes
        a_size += boarding_passes_sizes


    # transfer new expense variables to stored DataFrame
    if len(st.session_state.expenses.columns) == 5:
        new_df = pd.DataFrame(columns=["Category", "Description", "Paid amount", "Currency", "Attachments"],
                              data=[[deepcopy(category), 
                                     deepcopy(description), 
                                     deepcopy(amount), 
                                     deepcopy(currency), 
                                     attachment_names]])
    elif len(st.session_state.expenses.columns) == 7:
        new_df = pd.DataFrame(columns=["Category", "Description", "Paid amount", "Currency", "Exchange rate", "Paid amount (EUR)", "Attachments"],
                              data=[[deepcopy(category), 
                                     deepcopy(description), 
                                     deepcopy(amount), 
                                     deepcopy(currency), 
                                     deepcopy(exchange_rate),
                                     round(amount * exchange_rate, 2),
                                     attachment_names]])
    if st.session_state.expenses.shape[0] > 0:
        new_df = pd.concat((st.session_state.expenses, new_df), ignore_index=True)
    st.session_state.expenses = deepcopy(new_df)
    
    # store list of receipt documents in dictionary 
    st.session_state.attachments[new_df.shape[0] - 1] = (a_new, a_size)
    
    # clear fields in new entry widgets
    st.session_state.description = ""
    st.session_state.amount = 0.00
    st.session_state["file_uploader_key_1"] += 2
    st.session_state["file_uploader_key_2"] += 2
 
    # update summary table
    update_summary_table()
    return 


def delete_expense(ind: str):
    # drop selected expense from DataFrame
    st.session_state.expenses.drop(int(ind), inplace=True)
    st.session_state.expenses.reset_index(drop=True, inplace=True) 

    # delete list of attachments from the attachments dictionary
    if int(ind) in st.session_state.attachments: 
        del st.session_state.attachments[int(ind)]
        new_dict = {i: val for i, val in enumerate(st.session_state.attachments.values())}
        st.session_state.attachments = deepcopy(new_dict)
        del new_dict
    
    # delete kilometers if it is an own car entry
    if int(ind) in st.session_state.kilometers_own_car:
        del st.session_state.kilometers_own_car[int(ind)]

    # update summary table
    update_summary_table()
    return


# Main app.py ===============================================================
if __name__ == '__main__':
    # Intialize session_state variables:
    if "expenses" not in st.session_state:
        st.session_state.expenses = pd.DataFrame(columns=["Category", "Description", "Paid amount", "Currency", "Attachments"])
        st.session_state.attachments = {}
        st.session_state.expense_summary = pd.DataFrame(columns=["Category", "Amount"], 
                                                        data=[["Accommodation", 0.00],
                                                              ["Travel (flight, train, taxi, ...)", 0.00],
                                                              ["Meals", 0.00],
                                                              ["Total", 0.00]])
    if "file_uploader_key_1" not in st.session_state:
        st.session_state["file_uploader_key_1"] = 0
    if "file_uploader_key_2" not in st.session_state:
        st.session_state["file_uploader_key_2"] = 1
    if "uploaded_files" not in st.session_state:
        st.session_state["uploaded_files"] = []
    if "mission_data" not in st.session_state:
        st.session_state.mission_data = None
    if "kilometers_own_car" not in st.session_state:
        st.session_state.kilometers_own_car = {}
    # if "mission_cancelled" not in st.session_state:
    #     st.session_state.mission_cancelled = False
    # if "mission_modified" not in st.session_state:
    #     st.session_state.mission_modified = False

    # Configure layout of page, must be first streamlit call in script
    st.set_page_config(page_title="Mission Statement Tool", layout="wide", page_icon=":material/rocket_launch:")
    st.title("ATG/F4E-ext Mission Statement Tool")
    st.markdown("""
        <style>
        .stTextArea [data-baseweb=base-input] {
            background-color: gainsboro;
        }
        </style>
        """, unsafe_allow_html=True)

    # Approved mission statement
    with st.container(border=True):
        st.subheader("1. Approved Mission Request and notifications")
        cols_modifiers = st.columns(5, gap="large")
        with cols_modifiers[0]:
            miss_modified = st.toggle(label="Mission modified", key="mission_modified")
        with cols_modifiers[1]:
            miss_cancelled = st.toggle(label="Mission cancelled", key="mission_cancelled")
        cols_req = st.columns(2, gap="large")
        with cols_req[0]:
            miss_req = st.file_uploader("Please, upload your approved Mission Request:", type="pdf")
            if miss_req:
                try:
                    mission_data = parse_mission_request(miss_req)
                    if len(mission_data["currencies"]) > 1:
                        if "expenses" in st.session_state:
                            if len(st.session_state.expenses.columns) == 5:
                                if st.session_state.expenses.shape[0] > 0:
                                    st.session_state.expenses = pd.concat([st.session_state.expenses[["Category", "Description", "Paid amount", "Currency"]],
                                                                           pd.DataFrame({"Exchange rate": [1.0 for i in range(st.session_state.expenses.shape[0])]}),
                                                                           pd.DataFrame({"Paid amount (EUR)": st.session_state.expenses["Paid amount"].values}),
                                                                           st.session_state.expenses["Attachments"]], axis=1)
                                else:
                                    st.session_state.expenses = pd.DataFrame(columns=["Category", "Description", "Paid amount", "Currency", "Exchange rate", "Paid amount (EUR)", "Attachments"])
                except:
                    mission_data = None
                if st.session_state.mission_data is None:
                    st.session_state.mission_data = mission_data
                miss_req_imgs = convert_pdf2image(file=miss_req)
                st.session_state.mission_request = miss_req_imgs
                st.session_state.filename_out = miss_req.name.replace("Request", "Statement").replace(".pdf", ".docx").replace(".PDF", ".docx")
        with cols_req[1]:
            if miss_modified:
                miss_req_mod = st.file_uploader("If the accepted Mission Request was modified, please, upload your modified document:", type="pdf")
                if miss_req_mod:
                    try:
                        mission_data = parse_mission_request(miss_req)
                    except:
                        mission_data = None
                    st.session_state.mission_data = mission_data
                    miss_req_mod_list = convert_pdf2image(file=miss_req_mod)
                    st.session_state.modified_mission_request = miss_req_mod_list
        cols_req_2 = st.columns(2, gap="large")
        with cols_req_2[0]:
            notification = st.file_uploader("Please, upload a screenshot of the notification/greenlight from F4E to go on the mission:", type=["png", "jpg", "jpeg", "png", "bmp"])
            if notification:
                st.session_state.notification = notification
            notification_comment = st.text_area("Comments:", placeholder="Please, if any, add your comments to the notification screenshot. Otherwise, leave it blank.  \n"
                                                                        "NOTE: this is a placeholder and won\'t appear in your Mission Statement.")
            if notification_comment:
                st.session_state.notification_comment = notification_comment
        with cols_req_2[1]:
            if miss_cancelled:
                cancellation = st.file_uploader("Please, upload a screenshot of the written notification from F4E or the supplier that the mission has been canceled:", type=["png", "jpg", "jpeg", "png", "bmp"])
                if cancellation:
                    st.session_state.cancellation = cancellation

    # Expenses
    exchange_rate = 1.0
    currency = None
    if st.session_state.mission_data:
        currencies = st.session_state.mission_data["currencies"]
    else:
        currencies = ["EUR"]
    with st.container(border=True):
        st.subheader("2. Expenses")
        cols_exp = st.columns([6, 1], gap="small")
        with cols_exp[0]:
            with st.container(border=True):
            # with st.form("my_form", clear_on_submit=True):
                st.text("NEW EXPENSE")
                cols_new_exp = st.columns([0.7, 1.2, 0.5, 0.8, 1.2])
                with cols_new_exp[0]:
                    category = st.selectbox("Category", 
                                            options=["Accommodation",
                                                     "Flights",
                                                     "Train",
                                                     "Bus",
                                                     "Metro",
                                                     "Taxi",
                                                     "Rental car",
                                                     "Own car",
                                                     "Additional travel expenses",
                                                     "Meals"],
                                            key="category")
                with cols_new_exp[1]:
                    description = st.text_input("Description", key="description")
                with cols_new_exp[2]:
                    if category == "Own car":
                        amount = st.number_input("Kilometers travelled", format="%0.1f", key="amount")
                    else:
                        amount = st.number_input("Paid amount", format="%0.2f", key="amount")
                with cols_new_exp[3]:
                    if category != "Own car":
                        currency = st.selectbox("Currency", options=currencies)
                        if currency != "EUR":
                            if currency == "JPY":
                                exchange_rate = st.number_input("Exchange rage {} -> EUR:".format(currency), format="%0.6f", key="exchange_rate")
                            elif currency == "CHF":
                                exchange_rate = st.number_input("Exchange rage {} -> EUR:".format(currency), format="%0.5f", key="exchange_rate")
                            else:
                                exchange_rate = st.number_input("Exchange rage {} -> EUR:".format(currency), key="exchange_rate")
                            st.write("[ECB data](https://commission.europa.eu/funding-tenders/procedures-guidelines-tenders/information-contractors-and-beneficiaries/exchange-rate-inforeuro_en) (Watch out, choose proper conversion!!!)".format(currency.lower()))
                            # old page used: https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/eurofxref-graph-{}.en.html
                with cols_new_exp[4]:
                    if category == "Flights":
                        invoice = st.file_uploader("Invoice", accept_multiple_files=False, type=["pdf", "png", "jpg", "jpeg", "jfif", "tiff"], key=st.session_state["file_uploader_key_1"])
                        boarding_passes = st.file_uploader("Boarding pass(es)", accept_multiple_files=True, type=["pdf", "png", "jpg", "jpeg", "jfif", "tiff"], key=st.session_state["file_uploader_key_2"])
                        attachment = {"invoice": invoice, "boarding passes": boarding_passes}
                    elif category == "Own car":
                        attachment = st.file_uploader("Journey map screenshot", accept_multiple_files=False, type=["png", "jpg", "jpeg", "jfif", "tiff"], key=st.session_state["file_uploader_key_1"])
                    else:
                        attachment = st.file_uploader("Attachment", accept_multiple_files=False, type=["pdf", "png", "jpg", "jpeg", "jfif", "tiff"], key=st.session_state["file_uploader_key_1"])
        with cols_exp[1]:
            btn = st.button("ADD EXPENSE", 
                            icon=":material/add:",
                            use_container_width=True, 
                            on_click=add_expense, 
                            args=(category, description, amount, currency, attachment, exchange_rate))
            with st.container(border=True):
                st.text("DELETE EXPENSE")
                cols_del = st.columns([2, 1], vertical_alignment="bottom")
                with cols_del[0]:
                    del_ind = st.selectbox("Table entry:", options=list(range(st.session_state.expenses.shape[0])))
                with cols_del[1]:
                    st.button("", icon=":material/close:", on_click=delete_expense, args=(del_ind,))

        st.text("Declared expenses:")
        if len(st.session_state.expenses.columns) == 5:
            st.dataframe(st.session_state.expenses, 
                         column_config={"Category": st.column_config.TextColumn(width="small"),
                                        "Description": st.column_config.TextColumn(width="small"),
                                        "Paid amount": st.column_config.NumberColumn(format="%0.2f", width="small"),
                                        "Currency": st.column_config.TextColumn(width="small"),
                                        "Attachments": st.column_config.TextColumn(width="large")})
        elif len(st.session_state.expenses.columns) == 7:
            st.dataframe(st.session_state.expenses, 
                            column_config={"Category": st.column_config.TextColumn(width="small"),
                                        "Description": st.column_config.TextColumn(width="medium"),
                                        "Paid amount": st.column_config.NumberColumn(format="%0.2f", width="small"),
                                        "Currency": st.column_config.TextColumn(width="small"),
                                        "Exchange rate": st.column_config.NumberColumn(width="small"),
                                        "Paid amount (EUR)": st.column_config.NumberColumn(format="%0.2f", width="small"),
                                        "Attachments": st.column_config.TextColumn(width="large")})    
        st.text("Expense summary:")
        tbl_summary = st.dataframe(st.session_state.expense_summary, 
                                   column_config={"Category": st.column_config.TextColumn(),
                                                  "Amount": st.column_config.NumberColumn(format="%0.2f")},
                                   width=500,
                                   hide_index=True)

    # Mission statement generation
    with st.container(border=True):
        st.subheader("3. Mission statement")
        gen_btn = st.button("Check data and generate Mission Statement", icon=":material/description:")
        downloaded = False
        if gen_btn:
            # with open("mission_request", 'wb') as outp:  # Overwrites any existing file.
            #     pickle.dump(st.session_state.mission_request, outp, pickle.HIGHEST_PROTOCOL)
            # with open("modified_mission_request", 'wb') as outp:  # Overwrites any existing file.
            #     pickle.dump(st.session_state.modified_mission_request, outp, pickle.HIGHEST_PROTOCOL)
            # with open("notification", 'wb') as outp:  # Overwrites any existing file.
            #     pickle.dump(st.session_state.notification, outp, pickle.HIGHEST_PROTOCOL)
            # with open("mission_data", 'wb') as outp:  # Overwrites any existing file.
            #     pickle.dump(st.session_state.mission_data, outp, pickle.HIGHEST_PROTOCOL)
            # with open("expenses", 'wb') as outp:  # Overwrites any existing file.
            #     pickle.dump(st.session_state.expenses, outp, pickle.HIGHEST_PROTOCOL)
            # with open("attachments", 'wb') as outp:  # Overwrites any existing file.
            #     pickle.dump(st.session_state.attachments, outp, pickle.HIGHEST_PROTOCOL)
            # with open("expense_summary", 'wb') as outp:  # Overwrites any existing file.
            #     pickle.dump(st.session_state.expense_summary, outp, pickle.HIGHEST_PROTOCOL)

            # try:
            ms = generate_mission_statement()
            # except Exception as err:
            #     process_file_warning(err=err)
            # else:
            if ms:
                st.write(f":green[Mission Statement generated succesfully!  \n"
                        "You can now download the new document:]")
                downloaded = st.download_button(label="Download file", 
                                                data=ms.getvalue(), 
                                                file_name=ms.name,
                                                mime="docx",
                                                icon=":material/download:")
        if downloaded:
            st.write("File downloaded!")