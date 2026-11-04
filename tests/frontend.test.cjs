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
 const report={order_count:1,total_order_count:2,cancelled_count:1,revenue_vnd:100000,order_definition:'Đơn hợp lệ không hủy',granularity:'day',series:[{month:'2050-01-03',revenue:100000,orders:1}],best_sellers:[{product_name:'QA',units:2,revenue:100000}],low_stock:[],low_stock_threshold:5,latest_orders:[order]};
 const promo={code:'QA10',discount_type:'percent',discount_value:10,minimum_vnd:0,usage_limit:10,active:1,used_count:0,starts_at:'',expires_at:''};
 const customer={id:9,full_name:'TEST CUSTOMER',email:'qa@example.invalid',phone:'0000000000',spent_vnd:0,order_count:0,tier:'Thành viên mới',orders:[order],archived:0};
 const settings={store_name:'QA',low_stock_threshold:5};
 const switches={publicFilter:false,rejectStatus:false,quoteError:false,quoteOverride:null,csrfFailures:0,csrfRefreshError:false,mutationFailure:0,deleteRejected:false};const writes=[],calls=[];const storage=()=>{const m=new Map();return {getItem:k=>m.get(k)||null,setItem:(k,v)=>m.set(k,String(v)),removeItem:k=>m.delete(k)}};
 let location=new URL('https://qa.test/admin/products');
 const context={window,document,console,Intl,Date,URL,URLSearchParams,Set,Map,Blob,navigator:{},localStorage:storage(),sessionStorage:storage(),setTimeout:()=>1,clearTimeout:()=>{},get location(){return location},history:{pushState:(_,__,url)=>{location=new URL(url,location)}},FormData:class{},fetch:async(url,options={})=>{
  calls.push({url,method:options.method||'GET',headers:options.headers||{},body:options.body});
  if(options.method&&switches.mutationFailure)return {ok:false,status:switches.mutationFailure,json:async()=>({detail:'TEST REQUEST REJECTED'})};
  if(options.method&&switches.csrfFailures>0){switches.csrfFailures--;return {ok:false,status:403,json:async()=>({detail:{code:'csrf_expired',message:'TEST CSRF EXPIRED'}})}}
  let data;if(url==='/api/csrf'){if(switches.csrfRefreshError)return {ok:false,status:503,json:async()=>({detail:'TEST REFRESH FAILED'})};data={csrfToken:'QA-FRESH-TOKEN'}}
  else if(url==='/api/admin/uploads'&&options.method==='POST'){writes.push({url,body:options.body});data={image_url:'/uploads/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.webp'}}
  else if(options.method==='DELETE'){if(switches.deleteRejected)return {ok:false,status:409,json:async()=>({detail:'TEST ORDER EXISTS'})};const id=Number(url.split('/').pop());writes.push({url,body:JSON.parse(options.body)});products.splice(products.findIndex(p=>p.id===id),1);data={deleted:true,id}}
  else if(url==='/api/orders/quote'){if(switches.quoteError)return {ok:false,json:async()=>({detail:'TEST COUPON INVALID'})};data=switches.quoteOverride||{subtotal_vnd:400000,discount_vnd:40000,shipping_vnd:0,total_vnd:360000,coupon_code:'TEST10'}}
  else if(options.method==='POST'&&url.startsWith('/api/admin/')){writes.push({url,body:JSON.parse(options.body)});data={ok:true}}
  else if(options.method==='PATCH'){if(url.includes('/orders/')&&switches.rejectStatus)return {ok:false,json:async()=>({detail:'TEST TRANSITION REJECTED'})};writes.push({url,body:JSON.parse(options.body)});data=url.includes('/orders/')?{...order,status:JSON.parse(options.body).status}:{...products[0],...JSON.parse(options.body)}}
  else if(url==='/api/admin/products'||url.startsWith('/api/products?')||url==='/api/products')data=switches.publicFilter&&url!=='/api/admin/products'?products.filter(p=>p.active&&p.price_vnd>0):products;
  else if(url.startsWith('/api/products/'))data=products.find(p=>p.slug===url.split('/').pop());
  else if(url==='/api/admin/orders/7')data=order;
  else if(url.startsWith('/api/admin/dashboard')||url.startsWith('/api/admin/reports'))data=report;
  else if(url==='/api/admin/promotions')data=[promo];
  else if(url==='/api/admin/customers/9')data=customer;
  else if(url.startsWith('/api/admin/customers'))data=[customer];
  else if(url==='/api/admin/settings')data=settings;
  else if(url==='/api/admin/inventory')data=[];
  else if(url.startsWith('/api/admin/appointments'))data=[{id:4,status:'confirmed',service_type:'vet',service_date:'2050-01-03',time_slot:'10:00',owner_name:'QA',pet_name:'QA',phone:'0000000000'}];
  else if(url.startsWith('/api/admin/search'))data={products,orders:[order],customers:[customer]};
  else if(url==='/api/account/orders'||url==='/api/admin/orders')data=[order];
  else throw Error('Unexpected API '+url);
  return {ok:true,json:async()=>structuredClone(data)};
 }};
 window.scrollTo=()=>{};vm.createContext(context);
 for(const file of ['app.js','product-editor.js','checkout-pricing.js','design.js','admin.js'])vm.runInContext(fs.readFileSync(path.join(root,file),'utf8').replace(/init\(\);\s*$/,''),context);
 const run=code=>vm.runInContext(code,context);
 const prepareDialog=(id='product-editor')=>{const d=document.querySelector('#'+id),form=d.querySelector('form');Object.defineProperty(form,'elements',{value:Object.fromEntries([...form.querySelectorAll('[name]')].map(x=>[x.name,x]))});form.reportValidity=()=>true;return {d,form}};
 const proto=window.HTMLElement.prototype;
 Object.defineProperty(proto,'checked',{get(){return this.hasAttribute('checked')},set(value){this.toggleAttribute('checked',!!value)},configurable:true});
 proto.showModal=function(){this.setAttribute('open','')};proto.close=function(){this.removeAttribute('open');this.dispatchEvent(new window.Event('close'))};
 return {document,window,products,order,writes,calls,switches,promo,settings,report,run,prepareDialog,navigate:url=>{location=new URL(url,location)}};
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


test('quote preview renders server discount and final total before submission, and invalid coupon disables ordering',async()=>{
 const h=harness();h.navigate('/checkout');h.run(`STATE.products=${JSON.stringify(h.products)};STATE.cart=[{productId:6,name:'QA',price:120000,quantity:3}]`);
 await h.run('refreshCartQuote()');h.document.querySelector('#app').innerHTML=h.run('checkout()');
 assert.match(h.document.querySelector('[data-quote-discount]').textContent,/40\.000/);
 assert.match(h.document.querySelector('[data-quote-total]').textContent,/360\.000/);
 assert.equal(h.document.querySelector('[data-place-order]').disabled,false);
 assert.doesNotMatch(h.document.querySelector('#app').textContent,/Xác nhận khi đặt hàng/);
 h.document.querySelector('[name=name]').value='KEPT QA';h.switches.quoteError=true;await h.run('refreshCartQuote()');h.run('updateQuoteUI()');assert.equal(h.document.querySelector('[name=name]').value,'KEPT QA');
 assert.equal(h.document.querySelector('[data-place-order]').disabled,true);
 assert.match(h.document.querySelector('[data-order-pricing]').textContent,/TEST COUPON INVALID/);
});

test('rejected status change fetches authoritative server state instead of stale cached value',async()=>{
 const h=harness();h.navigate('/admin/orders');h.document.querySelector('#app').innerHTML=h.run(`orderTable([${JSON.stringify(h.order)}],true)`);
 h.order.status='preparing';h.switches.rejectStatus=true;
 const select=h.document.querySelector('[data-order-status]');select.querySelectorAll('option').forEach(x=>x.toggleAttribute('selected',x.value==='cancelled'));
 select.dispatchEvent(new h.window.Event('change',{bubbles:true}));await tick();await tick();
 assert.equal(h.document.querySelector('[data-order-status-label]').textContent,'Đang chuẩn bị');
 assert.equal(select.dataset.current,'preparing');assert.equal(select.value,'preparing');assert.equal(select.disabled,false);
});

test('all admin screens render functional scope, no placeholder tabs, real counts and terminal order controls',async()=>{
 const h=harness();h.run("STATE.user={role:'admin',full_name:'QA'}");
 for(const route of ['/admin','/admin/orders','/admin/products','/admin/inventory','/admin/customers','/admin/promotions','/admin/appointments?month=2050-01','/admin/reports','/admin/settings','/admin/search?q=QA']){
  h.navigate(route);await h.run('render()');const app=h.document.querySelector('#app');
  assert.equal(app.querySelector('.error-box'),null,route+': '+app.textContent);
  assert.ok(app.querySelector('.admin-content'),route);
  assert.doesNotMatch(app.textContent,/Mục này cần kết nối|Thiết lập nhanh|Chương trình ưu đãi|Phiếu nhập kho|Nhân viên dịch vụ/,route);
 }
 for(const status of ['delivered','cancelled']){
  h.document.querySelector('#app').innerHTML=h.run(`orderTable([{...${JSON.stringify(h.order)},status:'${status}'}],true)`);
  const select=h.document.querySelector('[data-order-status]');assert.equal(select.disabled,true);assert.equal(select.querySelectorAll('option').length,1);
 }
 h.navigate('/admin/products');await h.run('render()');const input=h.document.querySelector('#product-search');input.value='UNPRICED';input.dispatchEvent(new h.window.Event('input',{bubbles:true}));assert.match(h.document.querySelector('[data-result-count]').textContent,/1 \/ 2/);
 assert.match(h.document.querySelector('[data-admin-table]').textContent,/Nháp \/ chưa có giá/);
});

test('create product button opens complete form; cancel makes no write; save creates full product',async()=>{
 const h=harness();h.run("STATE.user={role:'admin'}");await h.run('render()');
 h.document.querySelector('[data-action=new-product]').dispatchEvent(new h.window.Event('click',{bubbles:true}));await tick();
 let {d,form}=h.prepareDialog();for(const name of ['sku','name','brand','category','description','specifications','compare_price_vnd','image'])assert.ok(form.elements[name],name);
 assert.equal(form.elements.sku.hasAttribute('readonly'),false);
 d.querySelector('[data-editor-close]').click();assert.equal(h.writes.length,0);
 await h.run('openProductEditor()');({d,form}=h.prepareDialog());
 for(const [name,value] of Object.entries({sku:'QA-NEW',slug:'qa-new',name:'QA NEW PRODUCT',brand:'QA BRAND',price_vnd:'90000',compare_price_vnd:'100000',stock:'5',description:'QA DESCRIPTION',specifications:'QA SPECS'}))form.elements[name].value=value;
 form.dispatchEvent(new h.window.Event('submit',{bubbles:true,cancelable:true}));await tick();await tick();
 assert.equal(h.writes.length,1);assert.equal(h.writes[0].url,'/api/admin/products');assert.equal(h.writes[0].body.active,1);assert.equal(h.writes[0].body.brand,'QA BRAND');assert.equal(h.writes[0].body.compare_price_vnd,100000);
});

test('inventory dialog rejects empty and zero input, saves signed delta with reason',async()=>{
 const h=harness();h.navigate('/admin/inventory');h.run("STATE.user={role:'admin'}");await h.run('render()');
 h.document.querySelector('[data-restock]').click();await tick();const {form}=h.prepareDialog('inventory-editor');
 form.elements.reason.value='QA adjustment';form.elements.productId.value='6';
 for(const value of ['', '0']){form.elements.delta.value=value;form.dispatchEvent(new h.window.Event('submit',{bubbles:true,cancelable:true}));await tick();assert.equal(h.writes.length,0)}
 form.elements.delta.value='-2';form.dispatchEvent(new h.window.Event('submit',{bubbles:true,cancelable:true}));await tick();assert.deepEqual(h.writes[0].body,{productId:6,delta:-2,reason:'QA adjustment'});
});

test('promotion and customer rows open populated forms; cancelling never writes',async()=>{
 const h=harness();h.run("STATE.user={role:'admin'}");
 h.navigate('/admin/promotions');await h.run('render()');h.document.querySelector('[data-edit-promo]').click();await tick();let {d,form}=h.prepareDialog('promotion-editor');assert.equal(form.elements.code.value,'QA10');for(const name of ['discount_type','discount_value','minimum_vnd','usage_limit','starts_at','expires_at','active'])assert.ok(form.elements[name]);d.querySelector('[data-editor-close]').click();
 h.navigate('/admin/customers');await h.run('render()');h.document.querySelector('[data-customer-detail]').click();await tick();({d,form}=h.prepareDialog('customer-editor'));assert.equal(form.elements.email.value,'qa@example.invalid');assert.match(d.textContent,/PPQA|Lịch sử đơn hàng/);d.querySelector('[data-editor-close]').click();assert.equal(h.writes.length,0);
});

test('report export is aggregate data, single point is legible, calendar has booking dots, appointment cannot regress',async()=>{
 const h=harness();h.run("STATE.user={role:'admin'}");h.navigate('/admin/reports');await h.run('render()');assert.match(h.document.querySelector('#app').textContent,/Chỉ có một kỳ dữ liệu/);assert.ok(h.document.querySelector('#admin-range-form [name=start]'));assert.ok(h.document.querySelector('[data-admin-export]'));
 const csv=h.run('reportCsvRows(STATE.adminReport)');assert.equal(csv[0].section,'summary');assert.ok(csv.some(r=>r.section==='revenue'));assert.ok(csv.some(r=>r.section==='best_seller'));assert.ok(!csv.some(r=>'customer_name' in r));
 h.navigate('/admin/appointments?month=2050-01');await h.run('render()');assert.match(h.document.querySelector('[data-book-day="2050-01-03"]').textContent,/● 1/);const select=h.document.querySelector('[data-appointment-status]');assert.equal(select.querySelector('[value=requested]'),null);
 h.document.querySelector('[data-book-day="2050-01-04"]').click();assert.match(h.document.querySelector('#appointment-day-count').textContent,/0 lịch hẹn/);
});

test('global search Enter navigates to actual search route',async()=>{
 const h=harness();h.run("STATE.user={role:'admin'}");await h.run('render()');const input=h.document.querySelector('#admin-search');assert.ok(input);input.value='QA';const event=new h.window.Event('keydown',{bubbles:true,cancelable:true});event.key='Enter';input.dispatchEvent(event);await tick();await tick();assert.match(h.run('location.pathname+location.search'),/\/admin\/search\?q=QA/);assert.match(h.document.querySelector('.admin-content').textContent,/Kết quả tìm kiếm/);
});

test('promotion edit preloads Vietnamese and timestamp dates, cancel preserves table dates with zero writes',async()=>{
 const h=harness();h.run("STATE.user={role:'admin'}");h.promo.starts_at='02/11/2026';h.promo.expires_at='2026-11-30T00:00:00Z';h.navigate('/admin/promotions');await h.run('render()');
 const before=h.document.querySelector('[data-admin-table]').textContent;assert.match(before,/02\/11\/2026 → 30\/11\/2026/);
 for(let i=0;i<2;i++){h.document.querySelector('[data-edit-promo]').click();await tick();const {d,form}=h.prepareDialog('promotion-editor');assert.equal(form.elements.starts_at.value,'2026-11-02');assert.equal(form.elements.expires_at.value,'2026-11-30');d.querySelector('[data-editor-close]').click();await h.run('render()');assert.equal(h.document.querySelector('[data-admin-table]').textContent,before)}
 assert.equal(h.writes.length,0);assert.throws(()=>h.run("couponDateInput('unreadable date')"));
});

test('settings displays actual contacts, missing contacts are optional and explain blank preservation',async()=>{
 const h=harness();h.run("STATE.user={role:'admin'}");h.navigate('/admin/settings');await h.run('render()');
 for(const key of ['support_phone','support_email','store_address'])assert.equal(h.document.querySelector(`[name=${key}]`).hasAttribute('required'),false);
 Object.assign(h.settings,{support_phone:'0000000000',support_email:'qa@example.invalid',store_address:'QA ADDRESS'});await h.run('render()');for(const key of ['support_phone','support_email','store_address'])assert.equal(h.document.querySelector(`[name=${key}]`).value,h.settings[key]);
 assert.match(h.document.querySelector('#settings-form').textContent,/trống không xóa dữ liệu đã lưu/);
});

test('public shop, home and favorites render only catalog entries returned as published and priced',async()=>{
 const h=harness();h.switches.publicFilter=true;h.products.push({...h.products[0],id:11,name:'QA DRAFT HIDDEN',slug:'qa-draft',active:0});h.run('STATE.favorite=new Set([6,10,11])');
 for(const expression of ['home()','shop()','favorites()']){const html=await h.run(expression);assert.doesNotMatch(html,/TEST UNPRICED PRODUCT|QA DRAFT HIDDEN/);assert.match(html,/TEST PRODUCT/)}
});

test('report reconciliation and CSV include explicit financial bridge and legacy discrepancy warning',async()=>{
 const h=harness();h.run("STATE.user={role:'admin'}");h.report.reconciliation={items_gross_vnd:90000,subtotal_vnd:91000,discount_vnd:1000,shipping_vnd:10000,subtotal_difference_vnd:1000,total_difference_vnd:0,recorded_total_vnd:100000,orders_needing_review:[{order_code:'QA-GAP',subtotal_difference_vnd:1000,total_difference_vnd:0}]};h.navigate('/admin/reports');await h.run('render()');
 const section=h.document.querySelector('.report-reconciliation');assert.match(section.textContent,/1 đơn lịch sử cần đối soát/);assert.match(section.textContent,/Giảm giá \(trừ\)/);assert.match(section.textContent,/Phí giao hàng \(cộng\)/);assert.match(section.textContent,/100\.000/);assert.match(h.document.querySelector('thead').textContent,/trước giảm \/ phí ship/);
 const csv=h.run('reportCsvRows(STATE.adminReport)');assert.ok(csv.some(r=>r.section==='reconciliation'&&r.label==='subtotal_difference_vnd'&&r.revenue_vnd===1000));
});

test('public support uses configured store contacts, no hardcoded design contacts, and escapes data',()=>{
 const h=harness();let html=h.run('support()');assert.match(html,/liên hệ chưa được cửa hàng cấu hình/);assert.doesNotMatch(html,/1900|support@pawpaw.vn|tel:/);
 h.run("syncStoreSettings({support_phone:'0000000000',support_email:'qa@example.invalid',store_address:'<QA ADDRESS>',free_shipping_from_vnd:'400000'})");
 html=h.run('support()');assert.match(html,/tel:0000000000/);assert.match(html,/qa@example.invalid/);assert.match(html,/&lt;QA ADDRESS&gt;/);assert.equal(h.run('STATE.freeShippingFrom'),400000);
 assert.doesNotMatch(h.run('footer()'),/1900|support@pawpaw.vn|Trần Thái Tông/);
 h.run("syncStoreSettings({support_phone:'not a phone'})");assert.doesNotMatch(h.run('contactPhoneButton()'),/href=/);
});

test('promotion dialog discloses actual database dates and explicitly explains unlimited dates',async()=>{
 const h=harness();h.promo.starts_at='2027-01-02';h.promo.expires_at='2027-01-31';await h.run("openPromotionEditor('QA10')");let {d,form}=h.prepareDialog('promotion-editor');assert.equal(form.elements.starts_at.value,'2027-01-02');assert.match(d.querySelector('[data-promotion-date-source]').textContent,/02\/01\/2027 → 31\/01\/2027/);d.querySelector('[data-editor-close]').click();
 h.promo.starts_at='';h.promo.expires_at='';await h.run("openPromotionEditor('QA10')");({d,form}=h.prepareDialog('promotion-editor'));assert.equal(form.elements.expires_at.value,'');assert.match(d.querySelector('[data-promotion-date-source]').textContent,/Không giới hạn → Không giới hạn/);assert.equal(h.writes.length,0);
});

test('delete button asks for typed SKU; cancel/wrong SKU do nothing; confirmed delete removes row and closes editor',async()=>{
 const h=harness();h.run("STATE.user={role:'admin'};STATE.csrf='QA-CURRENT'");await h.run('render()');
 h.document.querySelector('[data-delete-product="6"]').click();await tick();let {d,form}=h.prepareDialog('product-delete-confirm');assert.match(d.textContent,/TEST PRODUCT|TEST-006/);d.querySelector('[data-editor-close]').click();assert.equal(h.writes.length,0);
 await h.run('openProductEditor(6)');h.document.querySelector('#product-editor [data-delete-product]').click();await tick();({d,form}=h.prepareDialog('product-delete-confirm'));
 form.elements.confirm_sku.value='WRONG';form.dispatchEvent(new h.window.Event('submit',{bubbles:true,cancelable:true}));await tick();assert.equal(h.writes.length,0);assert.match(d.querySelector('.editor-error').textContent,/SKU xác nhận không khớp/);
 h.switches.csrfFailures=1;form.elements.confirm_sku.value='TEST-006';form.dispatchEvent(new h.window.Event('submit',{bubbles:true,cancelable:true}));await tick();await tick();
 assert.equal(h.writes.length,1);assert.deepEqual(h.writes[0].body,{confirm_sku:'TEST-006',expected_stock:19});assert.equal(h.calls.filter(c=>c.method==='DELETE').length,2);
 assert.equal(h.document.querySelector('#product-editor'),null);assert.equal(h.document.querySelector('#product-delete-confirm'),null);assert.equal(h.document.querySelector('[data-edit-product="6"]'),null);
});

test('delete blocks known order links and server rejection keeps confirmation open',async()=>{
 const h=harness();h.products[0].order_count=1;await h.run('openProductDeletion(6)');let {d,form}=h.prepareDialog('product-delete-confirm');assert.equal(d.querySelector('[type=submit]').disabled,true);assert.match(d.textContent,/kể cả đơn hủy/);
 form.dispatchEvent(new h.window.Event('submit',{bubbles:true,cancelable:true}));await tick();assert.equal(d.querySelector('[type=submit]').disabled,true);assert.equal(h.writes.length,0);d.querySelector('[data-editor-close]').click();
 h.products[0].order_count=0;h.switches.deleteRejected=true;await h.run('openProductDeletion(6)');({d,form}=h.prepareDialog('product-delete-confirm'));form.elements.confirm_sku.value='TEST-006';form.dispatchEvent(new h.window.Event('submit',{bubbles:true,cancelable:true}));await tick();await tick();assert.match(d.querySelector('.editor-error').textContent,/TEST ORDER EXISTS/);assert.ok(h.document.querySelector('#product-delete-confirm'));assert.equal(h.writes.length,0);
});

test('expired CSRF during first create transparently refreshes once, preserves payload and avoids double submission',async()=>{
 const h=harness();h.run("STATE.csrf='QA-STALE';STATE.user={role:'admin'}");h.switches.csrfFailures=1;await h.run('openProductEditor()');const {form}=h.prepareDialog();
 for(const [name,value] of Object.entries({sku:'QA-CSRF',slug:'qa-csrf',name:'QA CSRF PRODUCT',price_vnd:'10000',compare_price_vnd:'0',stock:'3',description:'QA KEPT DESCRIPTION'}))form.elements[name].value=value;
 form.dispatchEvent(new h.window.Event('submit',{bubbles:true,cancelable:true}));form.dispatchEvent(new h.window.Event('submit',{bubbles:true,cancelable:true}));await tick();await tick();
 const attempts=h.calls.filter(c=>c.url==='/api/admin/products'&&c.method==='POST');assert.equal(attempts.length,2);assert.equal(attempts[0].body,attempts[1].body);assert.equal(attempts[0].headers['X-CSRF-Token'],'QA-STALE');assert.equal(attempts[1].headers['X-CSRF-Token'],'QA-FRESH-TOKEN');assert.equal(h.calls.filter(c=>c.url==='/api/csrf').length,1);assert.equal(h.writes.length,1);assert.equal(h.writes[0].body.description,'QA KEPT DESCRIPTION');
});

test('CSRF refresh failure retains dirty form and never submits product a second time',async()=>{
 const h=harness();h.run("STATE.csrf='QA-STALE'");h.switches.csrfFailures=1;h.switches.csrfRefreshError=true;await h.run('openProductEditor(6)');const {d,form}=h.prepareDialog();form.elements.name.value='QA KEPT NAME';form.elements.description.value='QA KEPT DESCRIPTION';
 form.dispatchEvent(new h.window.Event('submit',{bubbles:true,cancelable:true}));await tick();await tick();assert.equal(h.writes.length,0);assert.equal(form.elements.name.value,'QA KEPT NAME');assert.equal(form.elements.description.value,'QA KEPT DESCRIPTION');assert.equal(d.hasAttribute('open'),true);assert.equal(d.querySelector('[type=submit]').disabled,false);assert.match(d.querySelector('.editor-error').textContent,/Không thể làm mới phiên/);assert.equal(h.calls.filter(c=>c.method==='PATCH').length,1);
});

test('automatic retry is bounded and never retries auth, origin, conflict, server or network errors',async()=>{
 for(const status of [401,403,409,500]){const h=harness();h.run("STATE.csrf='QA-TOKEN'");h.switches.mutationFailure=status;await assert.rejects(h.run("api('/api/admin/products/6',{method:'PATCH',body:JSON.stringify({stock:1})})"),/TEST REQUEST REJECTED/);assert.equal(h.calls.filter(c=>c.method==='PATCH').length,1);assert.equal(h.calls.filter(c=>c.url==='/api/csrf').length,0)}
 const h=harness();h.run("STATE.csrf='QA-TOKEN'");h.switches.csrfFailures=2;await assert.rejects(h.run("api('/api/admin/products/6',{method:'PATCH',body:JSON.stringify({stock:1})})"),/TEST CSRF EXPIRED/);assert.equal(h.calls.filter(c=>c.method==='PATCH').length,2);assert.equal(h.calls.filter(c=>c.url==='/api/csrf').length,1);assert.equal(h.writes.length,0);
 h.run("fetch=async()=>{throw Error('QA NETWORK FAILURE')}");await assert.rejects(h.run("api('/api/admin/products/6',{method:'PATCH',body:'{}'})"),/QA NETWORK FAILURE/);
});

test('concurrent requests share CSRF refresh and binary upload retries the same immutable body once',async()=>{
 const h=harness();await h.run("Promise.all([api('/api/admin/inventory',{method:'POST',body:'{}'}),api('/api/admin/inventory',{method:'POST',body:'{}'})])");assert.equal(h.calls.filter(c=>c.url==='/api/csrf').length,1);assert.equal(h.writes.length,2);
 const upload=harness();upload.run("STATE.csrf='QA-STALE'");upload.switches.csrfFailures=1;await upload.run("api('/api/admin/uploads',{method:'POST',headers:{'Content-Type':'image/png'},body:new Blob(['QA IMAGE'],{type:'image/png'})})");const attempts=upload.calls.filter(c=>c.url==='/api/admin/uploads');assert.equal(attempts.length,2);assert.equal(attempts[0].body,attempts[1].body);assert.equal(attempts[1].headers['Content-Type'],'image/png');assert.equal(upload.writes.length,1);assert.equal(upload.writes[0].body,attempts[0].body);
});

test('catalog header and footer agree after CatLove Apply, zero matches and clearing filters',async()=>{
 const h=harness();h.switches.publicFilter=true;h.products[0].brand='CatLove';
 for(let i=0;i<9;i++)h.products.push({...h.products[0],id:20+i,name:'QA OTHER '+i,slug:'qa-other-'+i,brand:'PuppyCare'});
 h.navigate('/shop');await h.run('render()');assert.match(h.document.querySelector('[data-catalog-count]').textContent,/Hiển thị 10 sản phẩm/);
 const brand=h.document.querySelector('[name=brand-filter][value=CatLove]');brand.checked=true;brand.dispatchEvent(new h.window.Event('change',{bubbles:true}));
 assert.match(h.document.querySelector('.shop-title p').textContent,/Có 1 sản phẩm phù hợp/);assert.match(h.document.querySelector('[data-catalog-count]').textContent,/Hiển thị 1 sản phẩm/);
 h.document.querySelector('[data-action=apply-filters]').click();await tick();await tick();assert.match(h.run('location.search'),/brand=CatLove/);assert.match(h.document.querySelector('[data-catalog-count]').textContent,/Hiển thị 1 sản phẩm/);
 const price=h.document.querySelector('#price-filter');price.value='1';price.dispatchEvent(new h.window.Event('input',{bubbles:true}));assert.match(h.document.querySelector('.shop-title p').textContent,/Có 0 sản phẩm phù hợp/);assert.match(h.document.querySelector('[data-catalog-count]').textContent,/Hiển thị 0 sản phẩm/);assert.equal(h.document.querySelector('[data-filter-empty]').hidden,false);
 h.document.querySelector('[data-action=clear-filters]').click();await tick();await tick();assert.match(h.document.querySelector('[data-catalog-count]').textContent,/Hiển thị 10 sản phẩm/);
 h.products.splice(0,h.products.length);await h.run('render()');assert.match(h.document.querySelector('.shop-title p').textContent,/Có 0 sản phẩm phù hợp/);assert.match(h.document.querySelector('[data-catalog-count]').textContent,/Hiển thị 0 sản phẩm/);
});

test('cart and checkout display applied coupon terms from the server, never a hardcoded rate',async()=>{
 const h=harness();h.switches.quoteOverride={subtotal_vnd:320000,discount_vnd:32000,shipping_vnd:0,total_vnd:288000,coupon_code:'QA10',coupon_terms:{discount_type:'percent',discount_value:10,minimum_vnd:150000}};
 h.run(`STATE.products=${JSON.stringify(h.products)};STATE.cart=[{productId:6,name:'QA',price:320000,quantity:1}]`);
 await h.run('refreshCartQuote()');h.document.querySelector('#app').innerHTML=h.run('cart()');assert.match(h.document.querySelector('[data-coupon-terms]').textContent,/QA10 Giảm 10%/);assert.match(h.document.querySelector('[data-quote-discount]').textContent,/32\.000/);assert.match(h.document.querySelector('[data-quote-total]').textContent,/288\.000/);
 h.switches.quoteOverride={...h.switches.quoteOverride,discount_vnd:96000,total_vnd:224000,coupon_terms:{discount_type:'percent',discount_value:30,minimum_vnd:150000}};await h.run('refreshCartQuote()');h.run('updateQuoteUI()');assert.match(h.document.querySelector('[data-coupon-terms]').textContent,/Giảm 30%/);assert.doesNotMatch(h.document.querySelector('[data-coupon-terms]').textContent,/10%/);
 h.document.querySelector('#app').innerHTML=h.run('checkout()');assert.match(h.document.querySelector('.quote-coupon-terms').textContent,/Giảm 30%/);assert.match(h.document.querySelector('[data-quote-total]').textContent,/224\.000/);
 h.switches.quoteOverride={...h.switches.quoteOverride,coupon_code:'',coupon_terms:null,discount_vnd:0};await h.run('refreshCartQuote()');assert.doesNotMatch(h.run('couponTermsLabel()'),/PAWPAW10|10%|30%/);
});
