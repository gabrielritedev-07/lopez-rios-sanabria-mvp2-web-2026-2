// API REST mínima para Google Sheets. Copia este archivo al editor de Apps Script.
const POS_RESOURCES = ["productos", "ventas", "compras", "clientes", "proveedores", "categorias"];

function doGet(e) {
  try {
    const sheet = getPosSheet_(e);
    return json_({ success: true, data: readRows_(sheet) });
  } catch (error) {
    return json_({ success: false, message: error.message });
  }
}

function doPost(e) {
  const lock = LockService.getScriptLock();
  let locked = false;
  try {
    const sheet = getPosSheet_(e);
    const body = JSON.parse(e.postData.contents);
    if (!body || !body.action || !body.data) throw new Error("El cuerpo requiere action y data.");
    lock.waitLock(10000);
    locked = true;
    let data;
    if (body.action === "create") data = createRow_(sheet, body.data);
    else if (body.action === "update") data = updateRow_(sheet, body.data);
    else if (body.action === "delete") data = deleteRow_(sheet, body.data);
    else throw new Error("Acción no soportada: " + body.action);
    return json_({ success: true, data: data });
  } catch (error) {
    return json_({ success: false, message: error.message });
  } finally {
    if (locked) lock.releaseLock();
  }
}

function getPosSheet_(e) {
  const resource = e && e.parameter && e.parameter.resource;
  if (POS_RESOURCES.indexOf(resource) < 0) throw new Error("Recurso no permitido.");
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(resource);
  if (!sheet) throw new Error("No existe la pestaña: " + resource);
  if (sheet.getLastRow() < 1 || sheet.getLastColumn() < 1) throw new Error("La pestaña requiere encabezados en la primera fila.");
  return sheet;
}

function headers_(sheet) {
  const headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getDisplayValues()[0].map(String);
  if (headers.indexOf("id") < 0) throw new Error("La fila 1 debe incluir el encabezado id.");
  if (headers.some(function (h) { return !h; })) throw new Error("Los encabezados no pueden tener espacios vacíos.");
  return headers;
}

function readRows_(sheet) {
  const headers = headers_(sheet);
  if (sheet.getLastRow() < 2) return [];
  return sheet.getRange(2, 1, sheet.getLastRow() - 1, headers.length).getValues()
    .filter(function (row) { return row[headers.indexOf("id")] !== ""; })
    .map(function (row) { const record = {}; headers.forEach(function (h, i) { record[h] = row[i]; }); return record; });
}

function createRow_(sheet, data) {
  const headers = headers_(sheet);
  if (!data.id) throw new Error("Cada registro requiere un id generado por el frontend.");
  if (findRow_(sheet, data.id) > 0) throw new Error("Ya existe un registro con ese id.");
  const row = headers.map(function (h) { return Object.prototype.hasOwnProperty.call(data, h) ? data[h] : ""; });
  sheet.appendRow(row);
  return data;
}

function updateRow_(sheet, data) {
  if (!data.id) throw new Error("La actualización requiere id.");
  const rowNumber = findRow_(sheet, data.id);
  if (rowNumber < 2) throw new Error("No se encontró el registro para actualizar.");
  const headers = headers_(sheet);
  const row = sheet.getRange(rowNumber, 1, 1, headers.length).getValues()[0];
  headers.forEach(function (h, i) { if (Object.prototype.hasOwnProperty.call(data, h)) row[i] = data[h]; });
  sheet.getRange(rowNumber, 1, 1, headers.length).setValues([row]);
  const saved = {}; headers.forEach(function (h, i) { saved[h] = row[i]; });
  return saved;
}

function deleteRow_(sheet, data) {
  if (!data.id) throw new Error("La eliminación requiere id.");
  const rowNumber = findRow_(sheet, data.id);
  if (rowNumber < 2) throw new Error("No se encontró el registro para eliminar.");
  sheet.deleteRow(rowNumber);
  return { id: String(data.id), deleted: true };
}

function findRow_(sheet, id) {
  const idColumn = headers_(sheet).indexOf("id") + 1;
  if (sheet.getLastRow() < 2) return -1;
  const values = sheet.getRange(2, idColumn, sheet.getLastRow() - 1, 1).getDisplayValues();
  const found = values.findIndex(function (row) { return String(row[0]) === String(id); });
  return found < 0 ? -1 : found + 2;
}

function json_(value) {
  return ContentService.createTextOutput(JSON.stringify(value)).setMimeType(ContentService.MimeType.JSON);
}
