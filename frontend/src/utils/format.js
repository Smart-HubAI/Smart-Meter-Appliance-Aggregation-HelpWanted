/**
 * Reusable number formatting utilities for the Tata Power Energy Dashboard.
 * All display-only formatting — never modifies stored/calculated values.
 *
 * Rules:
 *  - Strip unnecessary trailing zeros: 25.00 → "25", 18.50 → "18.5", 7.10 → "7.1"
 *  - Percentages: max 2 decimal places
 *  - Energy (kWh): max 2 decimal places
 *  - Power (kW/kVA/kVAR): max 2 decimal places
 *  - Currency (₹): max 2 decimal places
 *  - Power Factor: max 3 decimal places
 *  - Confidence: whole number percentage
 *  - Counts: integer with comma separator
 */

/**
 * Format a number to a given max decimal precision, stripping trailing zeros.
 * @param {number|null|undefined} value
 * @param {number} decimals - max decimal places (default 2)
 * @returns {string}
 */
export function fmtNum(value, decimals = 2) {
  if (value == null || value === undefined || isNaN(value)) return "—";
  const n = Number(value);
  if (!isFinite(n)) return "—";
  // toFixed then parseFloat strips trailing zeros
  return parseFloat(n.toFixed(decimals)).toString();
}

/**
 * Format as percentage: 35.275052785429004 → "35.28"
 * Caller appends "%" in JSX.
 */
export function fmtPct(value, decimals = 2) {
  return fmtNum(value, decimals);
}

/**
 * Format kWh value: 116.412345 → "116.41"
 */
export function fmtKwh(value) {
  return fmtNum(value, 2);
}

/**
 * Format power value (kW/kVA/kVAR): 2 decimal places.
 */
export function fmtPower(value) {
  return fmtNum(value, 2);
}

/**
 * Format power factor: 3 decimal places (0.859).
 */
export function fmtPF(value) {
  return fmtNum(value, 3);
}

/**
 * Format as currency with ₹ symbol: ₹5,624.32
 * @param {number|null|undefined} value
 * @param {number} decimals - max decimal places (default 2)
 * @returns {string}
 */
export function fmtCurrency(value, decimals = 2) {
  if (value == null || value === undefined || isNaN(value)) return "₹0";
  const n = Number(value);
  if (!isFinite(n)) return "₹0";
  const formatted = parseFloat(n.toFixed(decimals));
  return "₹" + formatted.toLocaleString("en-IN", {
    minimumFractionDigits: 0,
    maximumFractionDigits: decimals,
  });
}

/**
 * Format confidence as whole number percentage: 0.856 → "86%"
 */
export function fmtConfidence(value) {
  if (value == null || value === undefined || isNaN(value)) return "—";
  return Math.round(Number(value) * 100) + "%";
}

/**
 * Format an integer count with comma separators: 1234 → "1,234"
 */
export function fmtCount(value) {
  if (value == null || value === undefined || isNaN(value)) return "0";
  return Math.round(Number(value)).toLocaleString();
}
