<div dir="rtl">

# غرفة الوكلاء

شاشة حية تعرض كل قعدة Claude Code شغالة على جهازك كشخصية صغيرة: منو شغال الحين، منو ينطر ردك، ومنو خلص دوره. تتحدث بروحها كل ثانيتين.

- **لوحة بالمتصفح** فيها الغرفة والشخصيات، وتحتها كروت لكل وكيل: شنو يسوي الحين، شنو خلص، وكم فحص نجح.
- **وضع العرض** للتصوير والعروض: يخفي الكلام الخاص والعناوين، والحركة تبقى حقيقية.
- **لوحة جانبية داخل تطبيق Claude** (تجريبي، ماك بس): نفس الغرفة جنب المحادثة.
- **كل شي على جهازك**: السيرفر يسمع على `127.0.0.1` بس، وما يرسل شي برا.

## اللي تحتاجه

- ماك او ويندوز او لينكس
- Python 3.9 او اليديد
- Claude Code (التطبيق او الطرفية)

## التركيب

نزل الريبو:

</div>

```bash
git clone https://github.com/0alfares082/agents-room.git
```

<div dir="rtl">

**ماك او لينكس:**

</div>

```bash
cd agents-room && ./scripts/install.sh
```

<div dir="rtl">

**ويندوز** (افتح PowerShell بمجلد الريبو):

</div>

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install.ps1
```

<div dir="rtl">

بعدها افتح الغرفة بالمتصفح:

</div>

```
http://127.0.0.1:8795/
```

<div dir="rtl">

السيرفر يرجع يشتغل بروحه كل ما تشغل الجهاز: بالماك عن طريق LaunchAgent، وبلينكس عن طريق خدمة systemd للمستخدم (او التشغيل التلقائي مع سطح المكتب اذا ما في systemd)، وبويندوز عن طريق اختصار بمجلد Startup.

## وضع العرض

ضيف `?show=1` على الرابط:

</div>

```
http://127.0.0.1:8795/?show=1
```

<div dir="rtl">

بهالوضع:

- العناوين تنخفي وتطلع بدالها «المشروع · مهمة 1». اذا تبي العناوين تبين، حط `"showTitles": true` بالاعدادات، وكل اسم حاطه بـ `showAliases` ينبدل بالاسم البديل.
- كلامك وكلام Claude ووصف الاوامر ينشال. يبقى بس نوع الشغل مثل «يشغل امر» او «يعدل ملف».
- الحذف يصير بالسيرفر نفسه، يعني الكلام الخاص ما يوصل الصفحة اصلا.

## الاعدادات

انسخ ملف المثال وعدله:

</div>

```bash
cp board/config.example.json board/config.json
```

<div dir="rtl">

| المفتاح | شنو يسوي |
|---|---|
| `projects` | يصنف القعدات حسب كلمات بالعنوان او الطلب. لكل مشروع اسم وكلمات ولون، و`showAs` هو الاسم اللي يطلع بوضع العرض. |
| `showTitles` | `true` يخلي عناوين القعدات تبين بوضع العرض. الافتراضي `false`: العناوين تنخفي. |
| `showAliases` | كلمات تنبدل بالعناوين بوضع العرض، مثل اسم عميل او اسم شخص. |
| `projectsDir` | مكان محادثات Claude Code. الافتراضي `~/.claude/projects`. |
| `ledgerDir` | اختياري: مجلد فيه ملفات `ledger.json` عشان يطلع شريط الفحوص. |

بعد ما تعدل الاعدادات، شغل سكربت التركيب مرة ثانية عشان يعيد تشغيل السيرفر.

## اللوحة الجانبية داخل تطبيق Claude (تجريبي، ماك بس)

</div>

```bash
./scripts/install.sh --mod
```

<div dir="rtl">

سكر تطبيق Claude وافتحه من يديد، وبعدها اكتب `/agents-room`. هالخطوة تضيف المود لملف `~/.claude/settings.json` وتاخذ نسخة احتياطية منه قبل. المودات ميزة تجريبية بـ Claude Code، فاذا نسختك ما تدعمها، لوحة المتصفح تشتغل عادي.

## الازالة

**ماك او لينكس:**

</div>

```bash
./scripts/uninstall.sh
```

<div dir="rtl">

**ويندوز:**

</div>

```powershell
powershell -ExecutionPolicy Bypass -File scripts\uninstall.ps1
```

<div dir="rtl">

## الاختبارات

كل تعديل ينجرب تلقائيا بـ GitHub Actions على ماك وويندوز ولينكس، مع Python 3.9 و 3.12، ويجرب سكربت التركيب والازالة لكل نظام. وتقدر تشغلها عندك:

</div>

```bash
python3 -m pytest -q board/tests
```

```bash
python3 board/tests/smoke.py
```

<div dir="rtl">

## الخصوصية

اللوحة تقرا محادثات Claude Code من جهازك عشان تعرف منو شغال. لا تفتح المنفذ `8795` للشبكة، ولا تشارك الشاشة العادية وفيها شغل عملاء: استخدم وضع العرض.

</div>

---

## English

A live room that shows every Claude Code session on your computer as a little character: who is working, who is waiting on you, who just finished. Local only (binds `127.0.0.1`). Runs on macOS, Windows and Linux with Python 3.9+.

- Install on macOS or Linux: `./scripts/install.sh`. On Windows: `powershell -ExecutionPolicy Bypass -File scripts\install.ps1`. Then open `http://127.0.0.1:8795/`. It starts again at login (LaunchAgent, systemd user service or desktop autostart, Startup shortcut).
- Show mode for recordings: `http://127.0.0.1:8795/?show=1` hides session titles by default and drops every private line server-side. Set `"showTitles": true` in `board/config.json` to keep titles, with the names in `showAliases` and each project's `showAs` swapped in.
- In-app pane (experimental, macOS only, needs Claude Code mods): `./scripts/install.sh --mod`, restart Claude, type `/agents-room`.
- Remove: `./scripts/uninstall.sh`, or `scripts\uninstall.ps1` on Windows.
- Tests run on every push in GitHub Actions on all three OSes with Python 3.9 and 3.12, including each installer. Locally: `python3 -m pytest -q board/tests` and `python3 board/tests/smoke.py`.
