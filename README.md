# Tasty Food Point website

Customer website plus a Flask backend that saves orders.

## Run it on your computer

1. Install Python 3 from python.org (tick "Add Python to PATH").
2. Open a terminal in this folder and run:

```
pip install -r requirements.txt
set ADMIN_PASSWORD=your-own-password      (Windows)
export ADMIN_PASSWORD=your-own-password   (Mac/Linux)
python app.py
```

- Website: http://localhost:5000
- Orders page for the shop owner: http://localhost:5000/admin
  Username is `admin` (change with `ADMIN_USER`), password is `ADMIN_PASSWORD`.
  If you do not set a password it is `changeme`. Change it before going online.
- To use another port: `set PORT=3000` then `python app.py`.

## Your food photos

Your photos are already in `static/images/`. To change one, replace the file and keep the same name:
`burger-large.jpg`, `shawarma.jpg`, `wings.jpg`, `burger-small.jpg`,
`paratha-roll.jpg`, `pakora.jpg`.
If a photo is missing, the site shows a drawing of that item.

## Change menu, prices, phone, hours or WhatsApp

Edit `menu.json` and save. No restart needed. Prices are always read from this
file on the server, so customers cannot change them in the browser.

- `"whatsapp_number"`: number with country code, no plus sign (923006824417).
  The WhatsApp order button opens a chat with the order already typed in.
- `"hours"`: shown in the footer.
- Items sold by weight use `"unit": "kg"` (quantity moves in 250 g steps).
  Everything else uses `"unit": "piece"`.
- `"desc"` is the short line under the item name. `"badge"` adds a small tag (like Spicy).
- `"image"` is the photo path. `"icon"` is the drawing used when the photo is missing:
  `burger`, `shawarma`, `roll`, `wings` or `pakora`.

## How ordering works

A customer picks items on the form (or taps "Order Now" on a menu card), enters
name, phone and address, and submits. The order is saved in `orders.db`. The shop
sees it on the `/admin` page, which refreshes every 20 seconds, and can call the
customer, then mark the order Preparing, Done or Cancelled. Payment is cash.

## Files

- `app.py`: backend (menu API, order checks, SQLite storage, admin login)
- `menu.json`: shop details and menu
- `static/index.html`, `static/style.css`, `static/app.js`: the customer website
- `static/images/`: your food photos
- `admin.html`: the orders page for the shop
- `orders.db`: created automatically on first run, holds all orders

## Going online

The built-in server is for testing. For a real website, host it on a Python
host (for example PythonAnywhere, Render or a VPS) and run it with a production
server such as `gunicorn app:app`. Use HTTPS, because the orders page uses a password.
Note: Netlify only hosts static files, so it cannot run this backend.
