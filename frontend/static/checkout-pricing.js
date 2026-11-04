/* Preview is calculated by the server using the same function as order creation. */
let quoteRequest=0;
function quoteReady(){return !!STATE.quote&&!STATE.quotePending&&!STATE.quoteError}
async function refreshCartQuote(){
 const request=++quoteRequest;STATE.quote=null;STATE.quoteError='';STATE.quotePending=true;updateQuoteUI();
 if(!STATE.cart.length){STATE.quotePending=false;return}
 try{
  const quote=await api('/api/orders/quote',{method:'POST',body:JSON.stringify({items:STATE.cart.map(x=>({productId:x.productId,quantity:x.quantity})),coupon:localStorage.getItem('pawpaw-coupon')||''})});
  if(request!==quoteRequest)return;STATE.quote=quote;
 }catch(error){if(request!==quoteRequest)return;STATE.quoteError=error.message}
 finally{if(request===quoteRequest)STATE.quotePending=false}
}
function couponTermsLabel(){
 const q=STATE.quote;
 if(!quoteReady()||!q.coupon_code||!q.coupon_terms)return 'Mức giảm và điều kiện được xác nhận theo cấu hình hiện tại khi áp dụng mã.';
 const terms=q.coupon_terms,amount=terms.discount_type==='percent'?terms.discount_value+'%':money(terms.discount_value);
 return `<b>${esc(q.coupon_code)}</b> Giảm ${esc(amount)}${terms.minimum_vnd?` · Đơn từ ${money(terms.minimum_vnd)}`:''}`;
}
function quotePricingRows(){
 if(!quoteReady())return `<p class="quote-message ${STATE.quoteError?'danger':''}" role="status">${esc(STATE.quoteError||'Đang tính tổng tiền…')}</p>`;
 const q=STATE.quote;
 return `<div><span>Tạm tính</span><b>${money(q.subtotal_vnd)}</b></div><div><span>Giảm giá${q.coupon_code?' ('+esc(q.coupon_code)+')':''}</span><b data-quote-discount>−${money(q.discount_vnd)}</b></div>${q.coupon_code?`<p class="quote-coupon-terms">${couponTermsLabel()}</p>`:''}<div><span>Phí giao hàng</span><b>${money(q.shipping_vnd)}</b></div><div class="summary-total"><span>Tổng thanh toán</span><b data-quote-total>${money(q.total_vnd)}</b></div>`;
}
function couponControls(){return `<div class="coupon"><input id="coupon" aria-label="Mã giảm giá" placeholder="Nhập mã giảm giá..." value="${esc(localStorage.getItem('pawpaw-coupon')||'')}"><button type="button" class="btn btn-green" data-action="coupon">Áp dụng</button><button type="button" class="text-link" data-action="clear-coupon">Bỏ mã</button></div>`}
function updateQuoteUI(){
 document.querySelectorAll('[data-coupon-terms]').forEach(box=>box.innerHTML=couponTermsLabel());
 document.querySelectorAll('[data-order-pricing]').forEach(box=>box.innerHTML=quotePricingRows());
 const submit=document.querySelector('[data-place-order]');if(submit){submit.disabled=!quoteReady();submit.textContent=quoteReady()?`Đặt hàng (${money(STATE.quote.total_vnd)})`:'Đang xác nhận tổng tiền'}
 document.querySelectorAll('[data-checkout-link]').forEach(link=>{link.setAttribute('aria-disabled',String(!quoteReady()));link.classList.toggle('is-disabled',!quoteReady())});
 const input=document.querySelector('#coupon');if(input&&document.activeElement!==input)input.value=localStorage.getItem('pawpaw-coupon')||'';
}

document.addEventListener('keydown',event=>{if(event.key==='Enter'&&event.target.id==='coupon'){event.preventDefault();document.querySelector('[data-action=\"coupon\"]')?.click()}});
