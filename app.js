const BOT_USERNAME = "Rise_avenbot";
const tg = window.Telegram && window.Telegram.WebApp;

if (tg) {
  tg.expand();
  tg.ready();
}

let accounts = [];
try {
  accounts = JSON.parse(localStorage.getItem("2fa_accounts") || "[]");
} catch (err) {
  accounts = [];
}
if (!accounts.length) {
  accounts = [{ name: "Тестовый аккаунт", secret: "JBSWY3DPEHPK3PXP" }];
  localStorage.setItem("2fa_accounts", JSON.stringify(accounts));
}

let currentAccountIndex = 0;
let currentCode = "000000";

function cleanSecret(value) {
  return String(value || "").replace(/\s+/g, "").toUpperCase();
}

function updateDropdown() {
  const select = document.getElementById("accountSelect");
  select.innerHTML = "";
  accounts.forEach((acc, idx) => {
    const opt = document.createElement("option");
    opt.value = String(idx);
    opt.textContent = acc.name;
    select.appendChild(opt);
  });
  select.value = String(currentAccountIndex);
}

function updateTOTP() {
  const acc = accounts[currentAccountIndex];
  const boxes = document.querySelectorAll(".otp-box");
  if (!acc) {
    boxes.forEach((box) => {
      box.textContent = "-";
    });
    return;
  }
  try {
    const totp = new OTPAuth.TOTP({
      secret: OTPAuth.Secret.fromBase32(cleanSecret(acc.secret)),
      digits: 6,
      period: 30
    });
    currentCode = totp.generate();
    boxes.forEach((box, i) => {
      box.textContent = currentCode[i] || "-";
    });
  } catch (err) {
    boxes.forEach((box) => {
      box.textContent = "!";
    });
  }
  const secondsRemaining = 30 - (Math.floor(Date.now() / 1000) % 30);
  const label = secondsRemaining < 10 ? "0" + secondsRemaining : String(secondsRemaining);
  document.getElementById("timerText").textContent = "0:" + label;
  document.getElementById("progressBar").style.width = (secondsRemaining / 30) * 100 + "%";
}

function copyCode() {
  const done = () => {
    const btnText = document.getElementById("copyBtnText");
    btnText.textContent = "Скопировано!";
    setTimeout(() => {
      btnText.textContent = "Скопировать код";
    }, 1500);
  };
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(currentCode).then(done).catch(done);
  } else {
    done();
  }
  if (tg && tg.HapticFeedback) {
    tg.HapticFeedback.notificationOccurred("success");
  }
}

function openModal() {
  document.getElementById("addModal").classList.remove("hidden");
}

function closeModal() {
  document.getElementById("addModal").classList.add("hidden");
}

function saveAccount() {
  const name = document.getElementById("newName").value.trim();
  const secret = cleanSecret(document.getElementById("newSecret").value);
  if (!name || !secret) {
    alert("Заполните оба поля");
    return;
  }
  try {
    OTPAuth.Secret.fromBase32(secret);
  } catch (err) {
    alert("Неверный формат ключа. Нужны буквы A-Z и цифры 2-7.");
    return;
  }
  accounts.push({ name: name, secret: secret });
  localStorage.setItem("2fa_accounts", JSON.stringify(accounts));
  currentAccountIndex = accounts.length - 1;
  updateDropdown();
  updateTOTP();
  closeModal();
  document.getElementById("newName").value = "";
  document.getElementById("newSecret").value = "";
}

function botLink(start) {
  const name = BOT_USERNAME.replace(/^@/, "");
  if (!name) return "";
  return start ? "https://t.me/" + name + "?start=" + start : "https://t.me/" + name;
}

function openLink(url) {
  if (!url) return;
  if (tg && tg.openTelegramLink) tg.openTelegramLink(url);
  else window.open(url, "_blank");
}

document.getElementById("accountSelect").addEventListener("change", () => {
  currentAccountIndex = parseInt(document.getElementById("accountSelect").value, 10) || 0;
  updateTOTP();
});
document.getElementById("addBtn").addEventListener("click", openModal);
document.getElementById("cancelBtn").addEventListener("click", closeModal);
document.getElementById("saveBtn").addEventListener("click", saveAccount);
document.getElementById("copyBtn").addEventListener("click", copyCode);
document.getElementById("openBotBtn").addEventListener("click", () => openLink(botLink("")));
document.getElementById("payBtn").addEventListener("click", () => openLink(botLink("pay")));

updateDropdown();
updateTOTP();
setInterval(updateTOTP, 1000);
