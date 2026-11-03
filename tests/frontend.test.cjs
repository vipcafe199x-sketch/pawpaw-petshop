// Synthetic fixtures only: no production customer, order, SKU or inventory data.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const {parseHTML}=require('linkedom');
const vm=require('node:vm');
const fs=require('node:fs');
const path=require('node:path');
const root=path.join(__dirname,'../frontend/static');
const tick=()=>new Promise(resolve=>setImmediate(resolve));

function harness(){
 const {window,document}=parseHTML('<html><body><div id="app"></div><div id="toast-root"></div></body></html>');
 const products=[{id:6,slug:'qa-test-product',name:'TEST PRODUCT',price_vnd:120000,stock:19,active:1,sku:'TEST-006',species:'Chó',category:'Đồ chơi'}, {id:10,slug:'qa-unpriced-product',name:'TEST UNPRICED PRODUCT',price_vnd:0,stock:7,active:1,sku:'TEST-010',species:'Mèo',category:'Phụ kiện'}];
 const order={id:7,order_code:'PPQA',status:'pending',created_at:'2026-11-03T16:41:04.092Z',customer_name:'TEST CUSTOMER',phone:'0000000000',total_vnd:79000,items:[],address:'TEST ADDRESS'};
 const writes=[];const storage=()=>{const m=new Map();return {getItem:k=>m.get(k)||null,setItem:(k,v)=>m.set(k,String(v)),removeItem:k=>m.delete(k)}};
 let location=new URL('https://qa.test/admin/products');
 const context={window,document,console,Intl,Date,URL,URLSearchParams,Set,Map,Blob,navigator:{},localStorage:storage(),sessionStorage:storage(),setTimeout:()=>1,clearTimeout:()=>{},get location(){return location},history:{pushState:(_,__,url)=>{location=new URL(url,location)}},FormData:class{},fetch:async(url,options={})=>{
  let data;if(options.method==='PATCH'){writes.push({url,body:JSON.parse(options.body)});data=url.includes('/orders/')?{...order,status:JSON.parse(options.body).status}:{...products[0],...JSON.parse(options.body)}}
  else if(url==='/api/admin/products'||url.startsWith('/api/products?')||url==='/api/products')data=products;
  else if(url.startsWith('/api/products/'))data=products.find(p=>p.slug===url.split('/').pop());
  else if(url==='/api/account/orders'||url==='/api/admin/orders')data=[order];
  else throw Error('Unexpected API '+url);
  return {ok:true,json:async()=>structuredClone(data)};
 }};
 window.scrollTo=()=>{};vm.createContext(context);
 for(const file of ['app.js','product-editor.js','design.js'])vm.runInContext(fs.readFileSync(path.join(root,file),'utf8').replace(/init\(\);\s*$/,''),context);
 const run=code=>vm.runInContext(code,context);
 const prepareDialog=()=>{const d=document.querySelector('#product-editor'),form=d.querySelector('form');Object.defineProperty(form,'elements',{value:Object.fromEntries([...form.querySelectorAll('[name]')].map(x=>[x.name,x]))});form.reportValidity=()=>true;return {d,form}};
 const proto=window.HTMLElement.prototype;
 proto.showModal=function(){this.setAttribute('open','')};proto.close=function(){this.removeAttribute('open');this.dispatchEvent(new window.Event('close'))};
 return {document,window,products,order,writes,run,prepareDialog,navigate:url=>{location=new URL(url,location)}};
}

test('product editor preloads values; cancel and blank submit never write; explicit save writes values',async()=>{
 const h=harness();await h.run('openProductEditor(6)');let {d,form}=h.prepareDialog();
 assert.equal(form.elements.price_vnd.value,'120000');assert.equal(form.elements.stock.value,'19');assert.equal(h.writes.length,0);
 d.querySelector('[data-editor-close]').dispatchEvent(new h.window.Event('click',{bubbles:true}));assert.equal(h.document.querySelector('#product-editor'),null);assert.equal(h.writes.length,0);
 await h.run('openProductEditor(6)');({d,form}=h.prepareDialog());form.elements.price_vnd.value='';form.dispatchEvent(new h.window.Event('submit',{bubbles:true,cancelable:true}));await tick();assert.equal(h.writes.length,0);
 form.elements.price_vnd.value='81000';form.elements.stock.value='40';form.dispatchEvent(new h.window.Event('submit',{bubbles:true,cancelable:true}));await tick();
 assert.equal(h.writes.length,1);assert.equal(h.writes[0].body.price_vnd,81000);assert.equal(h.writes[0].body.stock,40);
});

test('zero-price products are labelled, disabled and blocked by addToCart',async()=>{
 const h=harness();h.run(`STATE.products=${JSON.stringify(h.products)}`);
 const card=h.run('productCard(STATE.products[1])');assert.match(card,/Chưa có giá bán/);assert.match(card,/data-add="10" disabled/);
 const detail=await h.run("productPage('qa-unpriced-product')");assert.match(detail,/Chưa có giá bán/);assert.match(detail,/data-add="10"[^>]*disabled/);
 h.run('addToCart(10)');assert.equal(h.run('STATE.cart.length'),0);
});

test('shipping uses pre-discount subtotal and renders one consistent policy',()=>{
 const h=harness();assert.equal(h.run('shippingFee(330000)'),0);assert.equal(h.run('shippingFee(299000)'),0);assert.equal(h.run('shippingFee(298999)'),30000);
 h.run(`STATE.products=${JSON.stringify(h.products)};STATE.cart=[{productId:6,name:'QA',price:79000,quantity:5}]`);
 assert.match(h.run('checkout()'),/trước giảm giá/);assert.doesNotMatch(h.run('cart()'),/Chọn tất cả|checked disabled/);
 assert.match(h.run('money(149000)'),/149\.000\u00a0₫/);
 const services=h.run('services()');assert.match(services,/149\.000\u00a0₫/);
});

test('shop breadcrumb and account have no unfinished pets section',async()=>{
 const h=harness();h.navigate('/shop');assert.match(await h.run('shop()'),/›<\/span>Cửa hàng/);
 h.run("STATE.user={full_name:'QA',email:'qa@example.com'}");assert.doesNotMatch(h.run('account()'),/account-pets|Thêm hồ sơ thú cưng|Thú cưng của tôi/);
});

test('admin order status badge and details update without reloading; date is Vietnam local time',async()=>{
 const h=harness();h.navigate('/admin/orders');h.document.querySelector('#app').innerHTML=h.run(`orderTable([${JSON.stringify(h.order)}],true)`);
 const select=h.document.querySelector('[data-order-status]');select.querySelectorAll('option').forEach(x=>{if(x.value==='confirmed')x.setAttribute('selected','');else x.removeAttribute('selected')});
 select.dispatchEvent(new h.window.Event('change',{bubbles:true}));await tick();await tick();
 assert.equal(h.document.querySelector('.status').textContent,'Đã xác nhận');assert.equal(select.dataset.current,'confirmed');assert.equal(select.disabled,false);
 assert.match(h.run("localDateTime('2026-11-03T16:41:04.092Z')"),/23:41/);
 assert.doesNotMatch(h.document.querySelector('tbody').textContent,/T16:41/);
});
