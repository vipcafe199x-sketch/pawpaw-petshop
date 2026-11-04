function couponDateInput(value){
 if(!value)return '';const raw=String(value).trim();
 if(/^\d{4}-\d{2}-\d{2}(?:$|T| )/.test(raw))return raw.slice(0,10);
 const m=raw.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);if(m)return `${m[3]}-${m[2]}-${m[1]}`;
 throw Error('Ngày khuyến mãi không đọc được. Kiểm tra dữ liệu trước khi sửa.');
}
function couponDateLabel(value){const iso=couponDateInput(value);return iso?iso.split('-').reverse().join('/'):'Không giới hạn'}
/* Real forms. Opening/cancelling a dialog performs no writes. */
function adminField(name,label,value='',options=''){return `<label>${label}<input name="${name}" value="${esc(value)}" ${options}></label>`}
function adminTextArea(name,label,value=''){return `<label>${label}<textarea name="${name}" rows="4">${esc(value)}</textarea></label>`}
function adminCheck(name,label,checked){return `<label class="editor-active"><input type="checkbox" name="${name}" ${checked?'checked':''}>${label}</label>`}
function fieldValue(form,name){return form.elements[name].value.trim()}
function adminDialog(id,title,fields,save){
 if(document.getElementById(id))return;
 const dialog=document.createElement('dialog');dialog.id=id;dialog.className='admin-dialog';dialog.setAttribute('aria-label',title);
 dialog.innerHTML=`<form class="product-editor-form"><header><h2>${esc(title)}</h2><button type="button" data-editor-close aria-label="Đóng">×</button></header>${fields}<p class="editor-error" role="alert" hidden></p><footer><button type="button" class="btn btn-light" data-editor-close>Hủy</button><button type="submit" class="btn btn-green">Lưu thay đổi</button></footer></form>`;
 document.body.appendChild(dialog);let busy=false;
 dialog.querySelectorAll('[data-editor-close]').forEach(button=>button.addEventListener('click',event=>{event.stopPropagation();if(!busy)dialog.close()}));
 dialog.addEventListener('cancel',event=>{if(busy)event.preventDefault()});dialog.addEventListener('close',()=>dialog.remove());
 dialog.querySelector('form').addEventListener('submit',async event=>{
  event.preventDefault();event.stopPropagation();const form=event.currentTarget;if(busy||!form.reportValidity())return;
  const error=dialog.querySelector('.editor-error');error.hidden=true;busy=true;
  dialog.querySelectorAll('button').forEach(x=>x.disabled=true);
  try{await save(form);dialog.close();await render();toast('Đã lưu thay đổi')}
  catch(err){error.textContent=err.message;error.hidden=false}
  finally{busy=false;dialog.querySelectorAll('button').forEach(x=>x.disabled=false)}
 });
 dialog.showModal();return dialog;
}
async function openProductEditor(id=null,trigger=null){
 if(document.querySelector('#product-editor'))return;
 let product={name:'',sku:'',slug:'',price_vnd:'',compare_price_vnd:0,stock:0,active:1,category:'Phụ kiện',species:'Chó',brand:'',description:'',specifications:'',image_url:'',featured:0};
 try{if(id){product=(await api('/api/admin/products')).find(p=>p.id===Number(id));if(!product)throw Error('Không tìm thấy sản phẩm')}}catch(err){toast(err.message,'error');return}
 if(document.querySelector('#product-editor'))return;
 const p=product;
 const fields=`<div class="editor-grid">${adminField('sku','SKU',p.sku,`required maxlength="80" ${id?'readonly':''}`)}${id?'':adminField('slug','Đường dẫn (để trống để tạo tự động)',p.slug)}${adminField('name','Tên sản phẩm',p.name,'required minlength="3" maxlength="300"')}${adminField('brand','Thương hiệu',p.brand||'','maxlength="300"')}${adminField('category','Danh mục',p.category,'required list="product-categories"')}<datalist id="product-categories">${CATEGORIES.slice(1).map(x=>`<option value="${esc(x)}">`).join('')}</datalist>${adminField('species','Loài thú cưng',p.species,'required')}${adminField('price_vnd','Giá bán / giá khuyến mãi (₫)',p.price_vnd,'type="number" min="0" step="1" required')}${adminField('compare_price_vnd','Giá gốc gạch ngang (0 nếu không giảm)',p.compare_price_vnd||0,'type="number" min="0" step="1" required')}${adminField('stock','Tồn kho',p.stock,'type="number" min="0" step="1" required')}</div><label>Ảnh sản phẩm (JPEG/PNG/WebP, tối đa 5 MB)<input name="image" type="file" accept="image/jpeg,image/png,image/webp"></label><img class="editor-image" ${p.image_url?`src="${esc(p.image_url)}"`:'hidden'} alt="Xem trước ảnh sản phẩm"><label class="editor-active"><input name="remove_image" type="checkbox">Bỏ ảnh đã tải (dùng ảnh mặc định)</label>${adminTextArea('description','Mô tả sản phẩm',p.description)}${adminTextArea('specifications','Chi tiết / thông số sản phẩm',p.specifications||'')}${adminCheck('active','Đang kinh doanh (giá phải lớn hơn 0)',p.active)}${adminCheck('featured','Sản phẩm nổi bật',p.featured)}<p class="editor-help">Hủy không lưu. Ảnh chỉ được upload khi bấm Lưu. Giá 0 chỉ được lưu ở trạng thái nháp.</p>`;
 const dialog=adminDialog('product-editor',id?'Sửa sản phẩm':'Thêm sản phẩm',fields,async form=>{
  const body={};for(const name of ['name','brand','category','species','description','specifications'])body[name]=fieldValue(form,name);
  for(const name of ['price_vnd','compare_price_vnd','stock']){const value=fieldValue(form,name);if(!value||!Number.isInteger(Number(value))||Number(value)<0)throw Error('Nhập giá và tồn kho nguyên, không để trống');body[name]=Number(value)}
  body.active=form.elements.active.checked?1:0;body.featured=form.elements.featured.checked?1:0;
  if(body.active&&body.price_vnd<=0)throw Error('Giá bán phải lớn hơn 0 khi đang kinh doanh');
  if(body.compare_price_vnd&&body.compare_price_vnd<body.price_vnd)throw Error('Giá gốc không được thấp hơn giá bán');
  if(!id){body.sku=fieldValue(form,'sku');body.slug=fieldValue(form,'slug')}else body.expected_stock=p.stock;
  body.image_url=form.elements.remove_image.checked?'':p.image_url||'';
  const file=form.elements.image.files?.[0];
  if(file){if(file.size>5*1024*1024)throw Error('Ảnh tối đa 5 MB');const response=await fetch('/api/admin/uploads',{method:'POST',headers:{'Content-Type':file.type,'X-CSRF-Token':STATE.csrf},credentials:'same-origin',body:file});const data=await response.json();if(!response.ok)throw Error(data.detail||'Upload ảnh thất bại');body.image_url=data.image_url}
  await api('/api/admin/products'+(id?'/'+id:''),{method:id?'PATCH':'POST',body:JSON.stringify(body)});
 });
 if(dialog)dialog.querySelector('[name=image]').addEventListener('change',event=>{const file=event.target.files?.[0];if(!file)return;const reader=new FileReader();reader.onload=()=>{const img=dialog.querySelector('.editor-image');img.src=reader.result;img.hidden=false};reader.readAsDataURL(file)});
}
async function openInventoryEditor(id=null){
 try{
  const products=await api('/api/admin/products');
  const fields=`<label>Sản phẩm<select name="productId" required>${products.map(p=>`<option value="${p.id}" ${p.id===Number(id)?'selected':''}>${esc(p.sku)} · ${esc(p.name)} · Tồn ${p.stock}</option>`).join('')}</select></label>${adminField('delta','Điều chỉnh (+ nhập thêm / − xuất bớt)','','type="number" min="-10000" max="10000" step="1" required')}${adminField('reason','Lý do','','required minlength="2" maxlength="160"')}<p class="inventory-preview" role="status"></p>`;
  const dialog=adminDialog('inventory-editor','Điều chỉnh tồn kho',fields,async form=>{const raw=fieldValue(form,'delta'),delta=Number(raw);if(!raw||!Number.isInteger(delta)||delta===0||Math.abs(delta)>10000)throw Error('Nhập số nguyên khác 0, tối đa ±10.000');await api('/api/admin/inventory',{method:'POST',body:JSON.stringify({productId:Number(fieldValue(form,'productId')),delta,reason:fieldValue(form,'reason')})})});
  dialog?.addEventListener('input',()=>{const form=dialog.querySelector('form'),p=products.find(x=>x.id===Number(form.elements.productId.value));dialog.querySelector('.inventory-preview').textContent=p?`Tồn hiện tại: ${p.stock} → Dự kiến: ${p.stock+Number(form.elements.delta.value||0)}`:''});
 }catch(err){toast(err.message,'error')}
}
async function openPromotionEditor(code=null){
 try{
  const current=code?(await api('/api/admin/promotions')).find(x=>x.code===code):{code:'',discount_type:'percent',discount_value:10,minimum_vnd:0,usage_limit:0,starts_at:'',expires_at:'',active:1};if(!current)throw Error('Không tìm thấy mã');const p=current;
  adminDialog('promotion-editor',code?'Sửa khuyến mãi':'Tạo khuyến mãi',`${adminField('code','Mã ưu đãi',p.code,`required minlength="4" maxlength="40" ${code?'readonly':''}`)}<label>Loại<select name="discount_type"><option value="percent" ${p.discount_type==='percent'?'selected':''}>Phần trăm</option><option value="fixed" ${p.discount_type==='fixed'?'selected':''}>Số tiền (₫)</option></select></label><div class="editor-grid">${adminField('discount_value','Giá trị',p.discount_value,'type="number" min="1" step="1" required')}${adminField('minimum_vnd','Đơn tối thiểu (₫)',p.minimum_vnd,'type="number" min="0" step="1" required')}${adminField('usage_limit','Giới hạn lượt (0 = không giới hạn)',p.usage_limit,'type="number" min="0" step="1" required')}${adminField('starts_at','Ngày bắt đầu',couponDateInput(p.starts_at),'type="date"')}${adminField('expires_at','Ngày kết thúc',couponDateInput(p.expires_at),'type="date"')}</div>${adminCheck('active','Đang bật',p.active)}${code?adminCheck('clear_dates','Xác nhận bỏ giới hạn ngày đã lưu',false):''}<p>Đã dùng: ${p.used_count||0} lượt. Bỏ chọn Đang bật để tắt mã.</p>`,async form=>{const body={};for(const name of ['code','discount_type','starts_at','expires_at'])body[name]=fieldValue(form,name);for(const name of ['discount_value','minimum_vnd','usage_limit']){const value=fieldValue(form,name);if(!value||!Number.isInteger(Number(value)))throw Error('Nhập số nguyên, không để trống');body[name]=Number(value)}body.active=form.elements.active.checked?1:0;if(code&&form.elements.clear_dates.checked){body.clear_dates=1;body.starts_at='';body.expires_at=''}await api('/api/admin/promotions'+(code?'/'+encodeURIComponent(code):''),{method:code?'PATCH':'POST',body:JSON.stringify(body)})});
 }catch(err){toast(err.message,'error')}
}
async function openCustomerEditor(id){
 try{const c=await api('/api/admin/customers/'+id);adminDialog('customer-editor','Chi tiết khách hàng',`${adminField('full_name','Họ tên',c.full_name,'required minlength="2"')}${adminField('email','Email',c.email,'type="email" required')}${adminField('phone','Số điện thoại',c.phone)}${adminCheck('active','Tài khoản hoạt động',!c.archived)}<p>${esc(c.tier)} · ${c.order_count} đơn hợp lệ · ${money(c.spent_vnd)}</p><h3>Lịch sử đơn hàng</h3>${orderTable(c.orders)}<p class="editor-help">Ngừng tài khoản sẽ thu hồi phiên đăng nhập, giữ nguyên lịch sử đơn. Không xóa vĩnh viễn dữ liệu.</p>`,async form=>{await api('/api/admin/customers/'+id,{method:'PATCH',body:JSON.stringify({full_name:fieldValue(form,'full_name'),email:fieldValue(form,'email'),phone:fieldValue(form,'phone'),archived:form.elements.active.checked?0:1})})})}catch(err){toast(err.message,'error')}
}
