<div dir="rtl">

# غرفة الوكلاء

شاشة حية تعرض كل قعدة Claude Code شغالة على جهازك كشخصية صغيرة: منو شغال الحين، منو ينطر ردك، ومنو خلص دوره. تتحدث بروحها كل ثانيتين.

- **لوحة بالمتصفح** فيها الغرفة والشخصيات، وتحتها كروت لكل وكيل: شنو يسوي الحين، شنو خلص، وكم فحص نجح.
- **وضع العرض** للتصوير والعروض: يبدل اسماء عملائك باسماء ثانية ويخفي الكلام الخاص، والحركة تبقى حقيقية.
- **لوحة جانبية داخل تطبيق Claude** (اختياري): نفس الغرفة جنب المحادثة، تضغط على اي شخصية وتفتح قعدتها.
- **كل شي على جهازك**: السيرفر يسمع على `127.0.0.1` بس، وما يرسل شي برا.

## اللي تحتاجه

- جهاز Mac
- Python 3.9 او اليديد
- Claude Code (التطبيق او الطرفية)

## التركيب

</div>

```bash
git clone https://github.com/0alfares082/agents-room.git
```

```bash
cd agents-room && ./scripts/install.sh
```

<div dir="rtl">

بعدها افتح الغرفة بالمتصفح:

</div>

```
http://127.0.0.1:8795/
```

<div dir="rtl">

السيرفر يشتغل بروحه كل ما تشغل الجهاز.

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

بعد ما تعدل الاعدادات، اعد تشغيل السيرفر:

</div>

```bash
./scripts/install.sh
```

<div dir="rtl">

## اللوحة الجانبية داخل تطبيق Claude (تجريبي)

</div>

```bash
./scripts/install.sh --mod
```

<div dir="rtl">

سكر تطبيق Claude وافتحه من يديد، وبعدها اكتب `/agents-room`. هالخطوة تضيف المود لملف `~/.claude/settings.json` وتاخذ نسخة احتياطية منه قبل. المودات ميزة تجريبية بـ Claude Code، فاذا نسختك ما تدعمها، لوحة المتصفح تشتغل عادي.

## الازالة

</div>

```bash
./scripts/uninstall.sh
```

<div dir="rtl">

## الاختبارات

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

A live room that shows every Claude Code session on your Mac as a little character: who is working, who is waiting on you, who just finished. Local only (binds `127.0.0.1`).

- Install: `./scripts/install.sh`, then open `http://127.0.0.1:8795/`.
- Show mode for recordings: `http://127.0.0.1:8795/?show=1` hides session titles by default and drops every private line server-side. Set `"showTitles": true` in `board/config.json` to keep titles, with the names in `showAliases` and each project's `showAs` swapped in.
- In-app pane (experimental, needs Claude Code mods): `./scripts/install.sh --mod`, restart Claude, type `/agents-room`.
- Remove: `./scripts/uninstall.sh`. Tests: `python3 -m pytest -q board/tests` and `python3 board/tests/smoke.py`.
