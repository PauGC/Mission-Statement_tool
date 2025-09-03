import os
# set environment variables to fix problem with easyocr
# OMP: Error #15: Initializing libiomp5md.dll, but found libiomp5md.dll already initialized.
# os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
from babel.numbers import get_currency_symbol, get_territory_currencies
from copy import deepcopy
from datetime import datetime
import easyocr
from itertools import tee, chain
import io
import numpy as np
import pandas as pd
from pathlib import Path
from PIL import Image, ImageDraw
import pycountry
import pymupdf
# from qrdet import QRDetector
import re
import streamlit as st
import sys
# import torch

# avoid RunTime error raised by torch
# RuntimeError: Tried to instantiate class '__path__._path', but it does not exist! Ensure that it is registered via torch::class_
# torch.classes.__path__ = []

BILLABLE_TRANSPORT = ["Own car", "Rental car", "Bus", "Metro", "Taxi", "Train", "Plane", "Ship"]

# functions definition
@st.dialog("ERROR!")
def zero_expense_error(currency: str):
    st.write("The paid amount for the expenses shall be larger than 0.00 {}.  \n" \
             "Please, introduce a valid value in the \"Paid amount\" input box.".format(currency))
    if st.button("OK"):
        st.rerun()


@st.dialog("ERROR!", width="large")
def flight_error():
    st.write("The flight shall have the following documents attached:  \n" \
             "- Invoice with the amount payed,  \n" \
             "- Boading passes (1 or more depending on the number of flights taken).")
    st.write("Please, attach these documents before proceeding.")
    if st.button("OK"):
        st.rerun()


@st.dialog("ERROR!")
def attachment_error():
    st.write("Each expense shall be justified with at least a receipt/invoice.  \n"
             "Please, attach the required documents before proceeding.")
    if st.button("OK"):
        st.rerun()


@st.dialog("ERROR!")
def exchange_rate_error():
    st.write("If the currency of the expense is different than EUR, the exchange rate must be provided.  \n"
             "Please, provide the exchange rate before proceeding.")
    if st.button("OK"):
        st.rerun()


@st.dialog("ERROR!")
def image_format_error():
    st.write("Image formats accepted: png, jpeg, tiff.  \n"
             "Please, provide an image in one of the accepted formats.  \n"
             "Apologizes for the inconvenience...")
    if st.button("OK"):
        st.rerun()


@st.dialog("ERROR")
def check_attachment_error(err: Exception):
    st.write("{}".format(err.args[0]))
    if st.button("OK"):
        st.rerun()


@st.dialog("WARNING!")
def process_file_warning(err: str):
    st.write("{}".format(err.args[0]))
    if st.button("OK"):
        st.rerun()


@st.dialog("WARNING!")
def attachment_warning(amount: float, currency: str, confidence: float):
    st.write("The amount {:0.2f} {} could not be recognized in the attachment.  \n".format(amount, currency))
    st.write("This indicates that either the uploaded receipt does not correspond to the intended expense or that the image resolution of the uploaded receipt is not optimal (average text recognition confidence of {} %).".format(int(confidence * 100)))
    st.write("This expense will be added, but please, make sure that you uploaded the right receipt or that the receipt has a proper resolution and " \
             "that the text can be clearly recognized.")
    st.write("If want to correct this expense, delete the corresponding entry, and add it again with the correct value.")
    btn_ok = st.button("OK")
    if btn_ok:
        st.rerun()


def pairwise(iterable):
    a, b = tee(iterable)
    next(b, None)
    return zip(a, b)


def parse_mission_request(file: io.BytesIO | str) -> dict:

    title_pattern = re.compile(r"F4E-OMF-1159-01-01-\d+ Mission Request \#\d{2}")
    transport_pattern = re.compile(r"(Own car)|(Rental car \(rented by)|(Rental car)|(Bus)|(Metro)|(Taxi)|(Train)|(Plane)|(Ship)")
    pattern_date = re.compile(r"\d+/\d+/\d{4}")

    if isinstance(file, str):
        filename = file
        pdf = pymupdf.open(filename=file)
    elif isinstance(file, io.BytesIO):
        filename = file.name
        pdf = pymupdf.open(stream=file)
    # filename_out = "-".join(filename.split("-")[:-2]).strip().replace("Request", "Statement") + ".docx"
    employee_name = filename.split("-")[6].strip()
    title_result = title_pattern.search(filename)
    if title_result:
        title_label = title_result[0].replace("Request", "Statement").upper()
    else:
        raise ValueError("File name of provided Mission Request does not fulfill the expected structure. Please, check the name of the uploaded file again.")
    mission_data = {"employee name": employee_name,
                    "title label": title_label}

    pdf_text = ""
    for page in pdf.pages():
        pdf_text += page.get_text(sort=True)
    lines = np.array([line.strip() for line in pdf_text.split("\n") if line])

    # Get destination country and currency
    ind_0 = np.where(["Mission destination (address)" in line for line in lines])[0][0]
    ind_1 = np.where(["Participant/s" in line for line in lines])[0][0]
    destination_text = " ".join(lines[ind_0:ind_1])
    ind_country = np.where([country.name in destination_text for country in pycountry.countries])[0]
    country = (list(pycountry.countries)[ind_country[0]] if ind_country.size != 0 else False)
    currency = (get_territory_currencies(country.alpha_2)[0] if country else False)
    currencies = list(set(["EUR", currency]))
    mission_data.update({"country": country,
                         "currencies": currencies})

    # Get billable transport means used:
    mission_data.update({"transport": []})
    dates = []
    ind = np.where(lines == "Itinerary:")[0][0]
    for line in lines[ind + 3:]:
        if line.startswith("Time of final arrival +1 hour"):
            break
        if line.startswith("*") or line == "Return" or line.startswith("Origin"):
            continue
        else:
            transport_match = transport_pattern.search(line)
            if transport_match:
                if transport_match.group() in BILLABLE_TRANSPORT:
                    mission_data["transport"].append(transport_match.group())
            date_match = pattern_date.search(line)
            if date_match:
                dates.append(datetime.strptime(date_match.group(), "%d/%m/%Y").date())
    dates = np.unique(dates)
    start_date, end_date = dates.min(), dates.max()
    mission_data.update({"start date": start_date, 
                         "end date": end_date})


    # Get mission budget and check if:
    ind = np.where([line.startswith("Travel expenses") for line in lines])[0][0]
    _, num_days, _, _, _, total_budget = lines[ind + 1].split()
    mission_data.update({"number of days": int(num_days),
                         "total budget": float(total_budget.replace(".", "").replace(",", "."))})
    return mission_data


def convert_pdf2image(file: io.BytesIO, dpi: int = 200) -> list:
    pdf = pymupdf.open(stream=file)
    imgs_list = []
    for page in pdf:
        pix = page.get_pixmap(dpi=dpi)
        pil_img = pix.pil_image()
        f = io.BytesIO()
        f.name = "{} - page - {}.jpeg".format(".".join(file.name.split(".")[:-1]), page.number)
        pil_img.save(fp=f, format="jpeg")
        imgs_list.append(f)
    return imgs_list


def check_boarding_passes(files: list):
    imgs_list = []
    sizes_list = []
    for file in files:
        if file.type == "application/pdf":
            pdf = pymupdf.open(stream=file)
            for page in pdf.pages():
                pg_height = page.rect.width / 72 * 2.54
                pg_width = page.rect.height / 72 * 2.54
                if pg_height / pg_width > 1.0:
                    size = (None, 9.0)
                else:
                    size = (14.0, None)
                pix = page.get_pixmap(dpi=200)
                pil_img = pix.pil_image()
                f = io.BytesIO()
                f.name = "{} - page - {}.jpeg".format(".".join(file.name.split(".")[:-1]), page.number)
                pil_img.save(fp=f, format="jpeg")
                imgs_list.append(f)
                sizes_list.append(size)
        elif file.type.startswith("image"):
            im = Image.open(fp=file)
            im_size_pix = im.size
            if im_size_pix[1] / im_size_pix[0] > 1.0:
                size = (None, 9.0)
            else:
                size = (14.0, None)
            del im
            imgs_list.append(file)
            sizes_list.append(size)
    return imgs_list, sizes_list


def process_attachment_pdf(amount: float, file: io.BytesIO, dpi: int = 200):
    if amount >= 1e3:
        amount_pattern = re.compile(r".*({}\.{}[,\.]{}).*".format(int(amount / 1000), int(amount % 1000), "{:02d}".format(int(round(amount % 1, 2) * 100))),
                                    re.DOTALL)
    else:
        amount_pattern = re.compile(r".*({}[,\.]{}).*".format(int(amount), "{:02d}".format(int(round(amount % 1, 2) * 100))), re.DOTALL)
    pdf = pymupdf.open(stream=file)
    ocr_oks = []
    pdf_imgs = []
    img_sizes = []
    conf_vals = []
    for page in pdf.pages():
        pg_height = page.rect.width / 72 * 2.54
        pg_width = page.rect.height / 72 * 2.54
        result = amount_pattern.match(page.get_text())
        if result:
            # find amount text in page
            amount_txt = result.groups()[0]
            amount_loc = page.search_for(amount_txt)  # Units are in points, where 72 points is 1 inch.
            # draw rectangle around amount text
            for rect in amount_loc:
                page.add_rect_annot(rect)
            # estimate optimal page size according to recognized text
            avg_txt_height = np.average([abs(rect.y1 - rect.y0) for rect in amount_loc]) / 72 * 2.54  # cm
            height_cm = min(pg_height / avg_txt_height * 0.388, 20.0)  # cm
            width_cm = height_cm / pg_height * pg_width
            ocr_oks.append(True)
            conf_vals.append(1.0)
        else:
            height_cm = min(pg_height, 20.0)
            width_cm = height_cm / pg_height * pg_width
            ocr_oks.append(False)
            if page.get_text():
                conf_vals.append(1.0)
            else:
                conf_vals.append(0.0)
        if width_cm > 16.25:
            width_cm = 16.25
            height_cm = None
        else:
            width_cm = None
        img_sizes.append((width_cm, height_cm))
        pix = page.get_pixmap(dpi=dpi)
        pil_img = pix.pil_image()
        f = io.BytesIO()
        f.name = "{} - page - {}.jpeg".format(".".join(file.name.split(".")[:-1]), page.number)
        pil_img.save(fp=f, format="jpeg")
        pdf_imgs.append(f)
    return ocr_oks, pdf_imgs, img_sizes, conf_vals


def estimate_image_size(ocr_list: list, idx_match: list, img_size_pix: tuple):
    # Pt(12) = 0.423 cm
    # Pt(11) = 0.388 cm <<<<<
    if not idx_match is None:
        height_pix = np.average([ocr_list[ind][0][2][1] - ocr_list[ind][0][1][1] for ind in idx_match])
    else:
        height_pix = np.average([elem[0][2][1] - elem[0][1][1] for elem in ocr_list])
    height_cm = min(img_size_pix[1] / height_pix * 0.388, 20.0)  # cm
    width_cm = img_size_pix[0] / img_size_pix[1] * height_cm
    if width_cm > 16.25:
        width_cm = 16.25
        height_cm = None
    else:
        width_cm = None
    return width_cm, height_cm


def check_attachment(category: str, amount: float, attachment: io.BytesIO):  #, reader: easyocr.Reader = None):    
    # initialize output variables
    ocr_oks, attachments_new, im_size_cms, confidence_avgs = [], [], [], []

    # process attachments one by one
    # convert pdf to image
    if attachment.type == "application/pdf":
        ocr_oks, attachments_new, im_size_cms, confidence_avgs = process_attachment_pdf(amount=amount, file=attachment)
    elif attachment.type.startswith("image"):
        # reduce image size to default:
        print("Reduce image size...")
        sys.stdout.flush()
        img = Image.open(fp=attachment)
        img = img.convert("RGB")
        target_byte_count = 500000
        target_pixel_count = 2.8114 * target_byte_count
        scale_factor = target_pixel_count / (img.size[0] * img.size[1])
        scale_factor = (1 if scale_factor > 1 else scale_factor)
        sml_size = list([int(scale_factor * dim) for dim in img.size])
        img_small = img.resize(sml_size, resample=Image.LANCZOS)
        f = io.BytesIO()
        f.name = attachment.name.replace(attachment.name.split(".")[-1], "jpeg")
        img_small.save(fp=f, format="jpeg", optimize=True, quality=95)
        # attachment = deepcopy(f)
        del img

        print("Load reader...")
        sys.stdout.flush()
        try:
            reader = easyocr.Reader(['en', 'es', 'fr', 'it', 'de'], gpu=False)
        except Exception as err:
            print(err)
            sys.stdout.flush()
            raise err
        print("Read text with OCR reader...")
        sys.stdout.flush()
        try:
            attachment_text = reader.readtext(f.getvalue())  # attachment.read())
        except Exception as err:
            print(err)
            sys.stdout.flush()
            raise err
        confidence_avg = np.mean([w[2] for w in attachment_text])
        if amount >= 1e3:
            amount_pattern = r".*({}\.{}\s?[,\.]\s?{}).*".format(int(amount / 1000), int(amount % 1000), "{:02d}".format(int(round(amount % 1, 2) * 100)))
        else:
            amount_pattern = r".*({}\s?[,\.]\s?{}).*".format(int(amount), "{:02d}".format(int(round(amount % 1, 2) * 100)))
        match_res = [re.match(amount_pattern, w[1]) for w in attachment_text]
        if any(match_res):
            ocr_ok = True
            print("OCR successful and text recognized!!!")
            sys.stdout.flush()
            try:
                im = Image.open(fp=attachment)  # .read())
                im = im.convert('RGB')
                im_size_pix = im.size
                inds = np.where(match_res)[0]
                for ind in inds:
                    points = attachment_text[ind][0]
                    points.append(points[0])
                    points = [tuple(p) for p in points]
                    # im = Image.open("./resources/Lunch_25-03-2025.jfif")
                    im2 = ImageDraw.Draw(im)
                    for p0, p1 in pairwise(points):
                        im2.line([p0, p1], fill="red", width=2)
                f = io.BytesIO()
                f.name = attachment.name.replace(attachment.name.split(".")[-1], "jpeg")
                im.save(fp=f, format="jpeg")
                attachment = f
            except Exception as err:
                raise err
        else:
            print("OCR successful but text NOT recognized.")
            sys.stdout.flush()
            ocr_ok = False
            try:
                im = Image.open(fp=attachment)
                im = im.convert('RGB')
                im_size_pix = im.size
                inds = None
                f = io.BytesIO()
                f.name = attachment.name.replace(attachment.name.split(".")[-1], "jpeg")
                im.save(fp=f, format="jpeg")
                attachment = f
            except Exception as err:
                raise err
        # estimate size: if amount is detected, size adjusted according to specific 
        # amount text, otherwise adjusted to average size of overall recognized text
        if im_size_pix:
            im_size_cm = estimate_image_size(ocr_list=attachment_text, idx_match=inds, img_size_pix=im_size_pix)
        else:
            im_size_cm = (None, None)
        # append results to return lists
        ocr_oks = [ocr_ok]
        attachments_new = [attachment]
        im_size_cms = [im_size_cm]
        confidence_avgs = [confidence_avg]
    else:
        raise TypeError("Unrecognized file type")
    # print(ocr_oks, attachments_new, im_size_cms, confidence_avgs)
    return ocr_oks, attachments_new, im_size_cms, confidence_avgs


# ================================================================================================
# NOT USED =======================================================================================
# ================================================================================================
"""
def process_boardingpass(file: io.BytesIO):
    filename = "./resources/1721312743577.jpg"
    # filename = "./resources/BCN-FRA.PNG"
    img = cv2.imread(filename, cv2.IMREAD_GRAYSCALE)
    contours, hierarchy = cv2.findContours(image=img, mode=cv2.RETR_TREE, method=cv2.CHAIN_APPROX_SIMPLE)

    # approach 1 (identify squared contours with approx size)
    # area_total = img.shape[0] * img.shape[1]
    # areas_rel = np.array([cv2.contourArea(contour) / area_total for contour in contours])
    # inds = np.where((areas_rel > 0.3e-3) 
    #                 & (areas_rel < 0.25) 
    #                 & (np.array([cont.shape[0] for cont in contours]) >= 4) 
    #                 & (np.array([cont.shape[0] for cont in contours]) < 12)
    #                 & ([is_square(cont) for cont in contours]))[0]
    # contours_filt = [contours[i] for i in inds]

    # approach 2: using hierarchy
    inds_child = [int(i) for i in np.where(hierarchy[0][:, 2] != -1)[0]]
    bullseye = []
    for i, ind in enumerate(inds_child):
        child = int(hierarchy[0][ind, 2])
        bullseye.append([ind])
        if child in inds_child:
            j = inds_child.index(child)
            inds_child.pop(j)
        while child != -1:
            bullseye[i].append(child)
            child = int(hierarchy[0][child, 2])
            if child in inds_child:
                j = inds_child.index(child)
                inds_child.pop(j)
    if any(np.array([len(l) for l in bullseye]) == 6):
        outer_cont = contours[bullseye[np.where(np.array([len(l) for l in bullseye]) == 6)[0][0]][0]]
    x_min, x_max = [int(func([p[0][0] for p in outer_cont])) for func in [min, max]]
    y_min, y_max = [int(func([p[0][1] for p in outer_cont])) for func in [min, max]]
    size_x = abs(x_max - x_min)
    size_y = abs(y_max - y_min)
    img_crop = img[int(y_min - 2.0 * size_y):int(y_max + 2.0 * size_y), int(x_min - 2.0 * size_x):int(x_max + 2.0 * size_x)]
    # plt.imshow(img_crop, cmap="Greys")
    # plt.savefig("img.jpg", dpi=300)
    
    # with open("myTempFile.tmp",'w+b') as tempf:
    # # with tempfile.NamedTemporaryFile() as tempf:
    #     reader = zxing.BarCodeReader()
    #     tempf.write(file.getbuffer())
    #     barcode = reader.decode(tempf.name)
    # if barcode.raw:
    #     return True
    # else:
    #     return False



def is_square(contour: np.ndarray, rel_error: float = 0.05) -> bool:
    x_proj = np.diff([func([point[0][0] for point in contour]) for func in [np.amin, np.amax]])[0]
    y_proj = np.diff([func([point[0][1] for point in contour]) for func in [np.amin, np.amax]])[0]
    if 2 * abs(x_proj - y_proj) / (x_proj + y_proj) < rel_error:
        return True
    else:
        return False


def contour_center(contour: np.ndarray) -> np.ndarray:
    return np.mean([point[0][0] for point in contour]), np.mean([point[0][1] for point in contour])
"""