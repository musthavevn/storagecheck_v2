from flask import Blueprint, session, request

i18n_bp = Blueprint("i18n", __name__)

_I18N = {
  "vi": {
    "app_title":"Quản lý kho",
    "login":"Đăng nhập",
    "logout":"Đăng xuất",
    "username":"Tài khoản",
    "password":"Mật khẩu",
    "products":"Sản phẩm",
    "add_product":"Thêm sản phẩm",
    "stock_in":"Nhập kho",
    "cart":"Giỏ xuất",
    "preview":"Xem phiếu",
    "checkout":"Chốt trừ kho",
    "settings":"Cài đặt",
    "staff":"Nhân viên",
    "reports":"Báo cáo",
  },
  "en": {
    "app_title":"Inventory Manager",
    "login":"Login",
    "logout":"Logout",
    "username":"Username",
    "password":"Password",
    "products":"Products",
    "add_product":"Add product",
    "stock_in":"Stock IN",
    "cart":"Cart",
    "preview":"Preview",
    "checkout":"Checkout",
    "settings":"Settings",
    "staff":"Staff",
    "reports":"Reports",
  },
}

def t(key:str)->str:
    lang = session.get("lang","vi")
    return _I18N.get(lang,_I18N["vi"]).get(key,key)

@i18n_bp.app_context_processor
def inject():
    return {"t": t, "current_lang": lambda: session.get("lang","vi")}

@i18n_bp.post("/set-lang")
def set_lang():
    lang = request.form.get("lang","vi")
    session["lang"] = "en" if lang=="en" else "vi"
    return ("",204)