/**
 * Google Apps Script — License Server + Key Generator cho Auto CapCut
 */

// ═══════════════════════════════════════════════════════════════
//  MENU — Thêm menu vào Google Sheet
// ═══════════════════════════════════════════════════════════════
function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu("AutoCapCut")
    .addItem("Tạo 1 Key (1 máy, 1 năm)", "createKey1Seat")
    .addItem("Tạo 1 Key (3 máy, 1 năm)", "createKey3Seats")
    .addItem("Tạo 1 Key (tùy chỉnh...)", "createKeyCustom")
    .addSeparator()
    .addItem("Tạo 10 Key hàng loạt", "createBulk10")
    .addItem("Tạo 50 Key hàng loạt", "createBulk50")
    .addToUi();
}

function createKey1Seat() {
  _addKey(1, 365);
}

function createKey3Seats() {
  _addKey(3, 365);
}

function createKeyCustom() {
  var ui = SpreadsheetApp.getUi();

  var seatsResult = ui.prompt("Số máy (max_seats):", "Nhập số máy được dùng cùng key:", ui.ButtonSet.OK_CANCEL);
  if (seatsResult.getSelectedButton() !== ui.Button.OK) return;
  var seats = parseInt(seatsResult.getResponseText()) || 1;

  var daysResult = ui.prompt("Số ngày sử dụng:", "Nhập số ngày (365 = 1 năm):", ui.ButtonSet.OK_CANCEL);
  if (daysResult.getSelectedButton() !== ui.Button.OK) return;
  var days = parseInt(daysResult.getResponseText()) || 365;

  _addKey(seats, days);
}

function createBulk10() {
  _addBulk(10, 1, 365);
}

function createBulk50() {
  _addBulk(50, 1, 365);
}

function _addKey(maxSeats, days) {
  var key = _generateKey();
  var expires = _addDays(new Date(), days);
  var expiresStr = Utilities.formatDate(expires, Session.getScriptTimeZone(), "yyyy-MM-dd");

  var sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("keys");
  sheet.appendRow([key, maxSeats, expiresStr, "TRUE"]);

  SpreadsheetApp.getUi().alert(
    "Key đã tạo!\n\n" + key + "\n\nMax seats: " + maxSeats + "\nExpires: " + expiresStr
  );
}

function _addBulk(count, maxSeats, days) {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("keys");
  var expires = _addDays(new Date(), days);
  var expiresStr = Utilities.formatDate(expires, Session.getScriptTimeZone(), "yyyy-MM-dd");

  var keys = [];
  for (var i = 0; i < count; i++) {
    var key = _generateKey();
    sheet.appendRow([key, maxSeats, expiresStr, "TRUE"]);
    keys.push(key);
  }

  SpreadsheetApp.getUi().alert(
    "Đã tạo " + count + " key!\n\nMax seats: " + maxSeats + "\nExpires: " + expiresStr + "\n\nXem trong tab keys."
  );
}

function _generateKey() {
  var chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
  var parts = [];
  for (var p = 0; p < 4; p++) {
    var part = "";
    for (var i = 0; i < 4; i++) {
      part += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    parts.push(part);
  }
  return parts.join("-");
}

function _addDays(date, days) {
  var result = new Date(date);
  result.setDate(result.getDate() + days);
  return result;
}

// ═══════════════════════════════════════════════════════════════
//  API — License validation endpoints
// ═══════════════════════════════════════════════════════════════
function doPost(e) {
  try {
    var data = JSON.parse(e.postData.contents);
    var action = data.action;
    if (action === "activate") {
      return respond(activate(data.key, data.hardware_id));
    } else if (action === "validate") {
      return respond(validate(data.key, data.hardware_id));
    } else {
      return respond({ success: false, message: "Unknown action" });
    }
  } catch (err) {
    return respond({ success: false, message: err.toString() });
  }
}

function doGet(e) {
  return respond({ success: true, message: "AutoCapCut License Server OK" });
}

function activate(key, hardwareId) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var keysSheet = ss.getSheetByName("keys");
  var activationsSheet = ss.getSheetByName("activations");
  var keysData = keysSheet.getDataRange().getValues();
  var keyRow = null;
  for (var i = 1; i < keysData.length; i++) {
    if (keysData[i][0] === key) { keyRow = keysData[i]; break; }
  }
  if (!keyRow) return { success: false, message: "Key không tồn tại" };
  var maxSeats = keyRow[1] || 1;
  var expiresAt = keyRow[2] || "";
  var isActive = keyRow[3];
  if (isActive === false || isActive === "FALSE") return { success: false, message: "Key đã bị vô hiệu hóa" };
  if (expiresAt) {
    var expDate = new Date(expiresAt);
    if (expDate < new Date()) return { success: false, message: "Key đã hết hạn" };
  }
  var activationsData = activationsSheet.getDataRange().getValues();
  var currentSeats = 0;
  var alreadyActivated = false;
  for (var i = 1; i < activationsData.length; i++) {
    if (activationsData[i][0] === key) {
      if (activationsData[i][1] === hardwareId) alreadyActivated = true;
      currentSeats++;
    }
  }
  if (alreadyActivated) return { success: true, message: "Đã kích hoạt trước đó!", expires_at: expiresAt.toString() };
  if (currentSeats >= maxSeats) return { success: false, message: "Key đã đạt giới hạn thiết bị (" + maxSeats + ")" };
  activationsSheet.appendRow([key, hardwareId, new Date().toISOString()]);
  return { success: true, message: "Kích hoạt thành công!", expires_at: expiresAt.toString() };
}

function validate(key, hardwareId) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var keysSheet = ss.getSheetByName("keys");
  var activationsSheet = ss.getSheetByName("activations");
  var keysData = keysSheet.getDataRange().getValues();
  var keyRow = null;
  for (var i = 1; i < keysData.length; i++) {
    if (keysData[i][0] === key) { keyRow = keysData[i]; break; }
  }
  if (!keyRow) return { success: false, message: "Key không tồn tại" };
  if (keyRow[3] === false || keyRow[3] === "FALSE") return { success: false, message: "Key đã bị vô hiệu hóa" };
  var expiresAt = keyRow[2] || "";
  if (expiresAt) {
    var expDate = new Date(expiresAt);
    if (expDate < new Date()) return { success: false, message: "Key đã hết hạn" };
  }
  var activationsData = activationsSheet.getDataRange().getValues();
  for (var i = 1; i < activationsData.length; i++) {
    if (activationsData[i][0] === key && activationsData[i][1] === hardwareId) {
      return { success: true, message: "Valid", expires_at: expiresAt.toString() };
    }
  }
  return { success: false, message: "Thiết bị chưa được kích hoạt" };
}

function respond(data) {
  return ContentService.createTextOutput(JSON.stringify(data)).setMimeType(ContentService.MimeType.JSON);
}
