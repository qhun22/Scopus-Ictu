// Kiểm tra cú pháp DBML bằng thư viện chính thức @dbml/core (cài ở thư mục tạm: npm i @dbml/core --ignore-scripts).
// Dùng: node check_dbml.js <đường dẫn .dbml>   (cần NODE_PATH trỏ tới node_modules đã cài)
const {Parser} = require('@dbml/core');
const fs = require('fs');
const src = fs.readFileSync(process.argv[2], 'utf8');
try {
  const db = new Parser().parse(src, 'dbml');
  const s = db.schemas[0];
  console.log('DBML OK: tables=', s.tables.length, 'refs=', s.refs.length);
} catch (e) { console.log('DBML LỖI:', JSON.stringify(e.diags || e.message).slice(0,800)); }
