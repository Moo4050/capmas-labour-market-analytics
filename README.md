# بوابة CAPMAS لسوق العمل
Team Members 
Ghada Osama 
Abdel Fatah Gaber 
Rokaya Samy 
Abdel Hamid Nasser
Mustafa Ashraf

## طريقة التشغيل

### المتطلبات
- Python 3.8+
- SQL Server مع قاعدة بيانات `Labour_ForceDB`
- ODBC Driver 17 for SQL Server

### خطوات التشغيل

1. **ضع اللوجو** في مجلد `static/images/logo.png`

2. **شغّل الملف** `run.bat` بضغطة دبل كليك

3. **افتح المتصفح** على: `http://localhost:8000`

---

## بيانات الدخول الافتراضية

| النوع | البيانات |
|-------|----------|
| مدير (Admin) | username: `admin` / password: `admin123` |
| فرد | أي Individual_ID موجود في قاعدة البيانات |

---

## تخصيص الـ Admin Dashboard

افتح ملف `templates/admin.html` وعدّل الروابط:

```html
YOUR_TABLEAU_LINK_1  ← رابط داشبورد Tableau الأول
YOUR_TABLEAU_LINK_2  ← رابط داشبورد Tableau الثاني
YOUR_TABLEAU_LINK_3  ← رابط داشبورد Tableau الثالث
YOUR_CHATBOT_URL     ← رابط الـ Chatbot
YOUR_POWERAPPS_LINK  ← رابط Power Apps
```

---

## هيكل المشروع

```
capmas_portal/
├── main.py              ← الـ Backend (FastAPI)
├── requirements.txt     ← المكتبات
├── run.bat              ← ملف التشغيل
├── static/
│   ├── css/style.css    ← التصميم
│   └── images/logo.png  ← اللوجو (ضعه هنا)
└── templates/
    ├── login.html       ← صفحة الدخول
    ├── individual.html  ← صفحة الفرد
    └── admin.html       ← صفحة المدير
```
