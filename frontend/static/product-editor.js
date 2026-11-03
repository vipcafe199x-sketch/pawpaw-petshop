/* Explicit save only: opening, cancelling and dismissing this dialog never PATCH. */
async function openProductEditor(id, trigger){
 if(document.querySelector('#product-editor'))return;
 let product;
 try{product=(await api('/api/admin/products')).find(p=>p.id===id)}catch(error){toast(error.message,'error');return}
 if(document.querySelector('#product-editor'))return;
 if(!product){toast('Không tìm thấy sản phẩm','error');return}
 if(!['/admin/products','/admin/inventory'].includes(location.pathname))return;
 const dialog=document.createElement('dialog');dialog.id='product-editor';
 dialog.setAttribute('aria-labelledby','product-editor-title');
 dialog.innerHTML=`<form class="product-editor-form"><header><h2 id="product-editor-title">Sửa sản phẩm</h2><button type="button" data-editor-close aria-label="Đóng">×</button></header><p>${esc(product.sku)}</p><label>Tên sản phẩm<input name="name" required minlength="3" value="${esc(product.name)}"></label><div class="editor-grid"><label>Giá bán (₫)<input name="price_vnd" type="number" min="1" max="2147483647" step="1" required value="${product.price_vnd}"></label><label>Tồn kho<input name="stock" type="number" min="0" max="2147483647" step="1" required value="${product.stock}"></label></div><p class="editor-help">Giá bán phải lớn hơn 0. Tồn kho bằng 0 là hết hàng. Chỉ lưu khi bạn bấm “Lưu thay đổi”.</p><label class="editor-active"><input name="active" type="checkbox" ${product.active?'checked':''}>Đang kinh doanh</label><p class="editor-error" role="alert" hidden></p><footer><button type="button" class="btn btn-light" data-editor-close>Hủy</button><button type="submit" class="btn btn-green">Lưu thay đổi</button></footer></form>`;
 document.body.appendChild(dialog);
 let saving=false;
 dialog.querySelectorAll('[data-editor-close]').forEach(button=>button.addEventListener('click',event=>{event.stopPropagation();if(!saving)dialog.close()}));
 dialog.addEventListener('cancel',event=>{if(saving)event.preventDefault()});
 dialog.addEventListener('close',()=>{dialog.remove();if(trigger?.isConnected)trigger.focus()});
 dialog.querySelector('form').addEventListener('submit',async event=>{
  event.preventDefault();event.stopPropagation();
  if(saving)return;
  const form=event.currentTarget;if(!form.reportValidity())return;
  const price=form.elements.price_vnd.value.trim(),stock=form.elements.stock.value.trim();
  const error=dialog.querySelector('.editor-error');
  if(!price||!stock||!Number.isInteger(Number(price))||Number(price)<=0||!Number.isInteger(Number(stock))||Number(stock)<0){error.textContent='Nhập giá bán nguyên lớn hơn 0 và tồn kho nguyên không âm.';error.hidden=false;return}
  saving=true;error.hidden=true;dialog.querySelectorAll('button,input').forEach(x=>x.disabled=true);
  try{
   await api(`/api/admin/products/${id}`,{method:'PATCH',body:JSON.stringify({name:form.elements.name.value.trim(),price_vnd:Number(price),stock:Number(stock),active:form.elements.active.checked?1:0})});
   dialog.close();await render();toast('Đã cập nhật sản phẩm');
  }catch(err){error.textContent=err.message;error.hidden=false}
  finally{saving=false;dialog.querySelectorAll('button,input').forEach(x=>x.disabled=false)}
 });
 dialog.showModal();
}
