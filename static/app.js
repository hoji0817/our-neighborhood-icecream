const AREA_DATA = {
"수원시":["장안구","권선구","팔달구","영통구"],"성남시":["수정구","중원구","분당구"],
"고양시":["덕양구","일산동구","일산서구"],"용인시":["처인구","기흥구","수지구"],
"부천시":["원미구","소사구","오정구"],"안산시":["상록구","단원구"],"안양시":["만안구","동안구"],
"화성시":["동탄구","만세구","효행구","병점구"],"평택시":["팽성읍","비전동","고덕동"],
"의정부시":["의정부동","민락동","가능동"],"남양주시":["다산동","별내동","화도읍"],
"파주시":["운정동","금촌동","문산읍"],"김포시":["장기동","구래동","풍무동"],
"광주시":["경안동","태전동","오포읍"],"하남시":["미사동","감일동","덕풍동"],
"시흥시":["배곧동","정왕동","은행동"],"군포시":["산본동","금정동","당동"],
"오산시":["세교동","오산동","원동"],"이천시":["창전동","증포동","부발읍"],
"구리시":["갈매동","인창동","수택동"],"양주시":["옥정동","덕계동","회천동"],
"의왕시":["내손동","포일동","오전동"],"안성시":["공도읍","아양동","금산동"],
"포천시":["소흘읍","포천동","선단동"],"양평군":["양평읍","용문면"],
"여주시":["여흥동","오학동"],"동두천시":["생연동","지행동"],"과천시":["중앙동","별양동"],
"가평군":["가평읍","청평면"],"연천군":["전곡읍","연천읍"]
};
function fillDistrict(citySelect, districtSelect, selected="") {
  if (!citySelect || !districtSelect) return;
  const list = AREA_DATA[citySelect.value] || [];
  districtSelect.innerHTML = '<option value="">전체</option>';
  list.forEach(name => {
    const option = document.createElement("option"); option.value = name; option.textContent = name;
    if (name === selected) option.selected = true;
    districtSelect.appendChild(option);
  });
}
const citySelect = document.getElementById("citySelect");
const districtSelect = document.getElementById("districtSelect");
if (citySelect && districtSelect) {
  fillDistrict(citySelect, districtSelect, districtSelect.dataset.selected || "");
  citySelect.addEventListener("change", () => fillDistrict(citySelect,districtSelect));
}
const checkoutCity = document.getElementById("checkoutCity");
const checkoutDistrict = document.getElementById("checkoutDistrict");
if (checkoutCity && checkoutDistrict) {
  fillDistrict(checkoutCity, checkoutDistrict);
  checkoutCity.addEventListener("change", () => fillDistrict(checkoutCity,checkoutDistrict));
}
const CART_KEY = "iceCart";
function getCart(){ try { return JSON.parse(localStorage.getItem(CART_KEY) || "{}"); } catch { return {}; } }
function saveCart(cart){ localStorage.setItem(CART_KEY,JSON.stringify(cart)); updateCartCount(); }
function updateCartCount(){
  const node=document.getElementById("cartCount"); if(!node) return;
  node.textContent=Object.values(getCart()).reduce((a,b)=>a+Number(b),0);
}
function addToCart(id,name,price,stock,qty=1){
  const cart=getCart(); const key=String(id);
  if(Number(qty)<1 || Number(qty)>Number(stock)){ alert("재고 범위 안에서 수량을 선택해 주세요."); return; }
  const next=(Number(cart[key]||0)+Number(qty));
  if(next>Number(stock)){ alert("장바구니 수량이 현재 재고보다 많습니다."); return; }
  cart[key]=next; saveCart(cart); alert(name+" 상품을 장바구니에 담았습니다.");
}
document.querySelectorAll(".add-cart").forEach(btn=>btn.addEventListener("click",()=>addToCart(btn.dataset.id,btn.dataset.name,btn.dataset.price,btn.dataset.stock)));
const detailAdd=document.getElementById("detailAdd");
if(detailAdd) detailAdd.addEventListener("click",()=>{
  const qty=Number(document.getElementById("detailQty").value||1);
  addToCart(detailAdd.dataset.id,detailAdd.dataset.name,detailAdd.dataset.price,detailAdd.dataset.stock,qty);
});
const checkoutCart=document.getElementById("checkoutCart");
if(checkoutCart){
  const cart=getCart();
  const ids=Object.keys(cart).filter(id=>Number(cart[id])>0);
  const cartJson=document.getElementById("cartJson");
  const totals=document.getElementById("cartTotals");
  const checkoutForm=document.getElementById("checkoutForm");
  if(cartJson) cartJson.value=JSON.stringify(cart);
  if(!ids.length){
    checkoutCart.innerHTML='<p class="empty-text">장바구니가 비어 있습니다. <a href="/">상품을 먼저 담아 주세요.</a></p>';
    if(totals) totals.innerHTML='<p>상품 합계 <strong>0원</strong></p><p>배송비 <strong>0원</strong></p><p>최종 결제금액 <strong>0원</strong></p>';
    if(checkoutForm) checkoutForm.querySelector('button[type="submit"]').disabled=true;
  } else {
    fetch('/api/cart-details?ids='+encodeURIComponent(ids.join(',')))
      .then(response=>{ if(!response.ok) throw new Error('상품 정보를 불러오지 못했습니다.'); return response.json(); })
      .then(data=>{
        const products=data.products||[];
        const byId=Object.fromEntries(products.map(p=>[String(p.id),p]));
        const missing=ids.filter(id=>!byId[id]);
        if(missing.length){
          checkoutCart.innerHTML='<p class="notice error">판매가 중단되었거나 찾을 수 없는 상품이 장바구니에 있습니다. 해당 상품을 삭제하고 다시 담아 주세요.</p>';
          if(totals) totals.innerHTML='<p>상품 금액을 확인할 수 없어 최종 결제금액을 계산하지 못했습니다.</p>';
          return;
        }
        const lines=ids.map(id=>{
          const p=byId[id]; const qty=Number(cart[id]); const lineTotal=p.price*qty;
          return `<div class="cart-line"><div><strong>${escapeHtml(p.name)}</strong><div class="muted">${Number(p.price).toLocaleString('ko-KR')}원 × ${qty}개 = ${lineTotal.toLocaleString('ko-KR')}원</div></div><button type="button" class="btn tiny secondary" data-remove="${escapeHtml(id)}">삭제</button></div>`;
        }).join('');
        checkoutCart.innerHTML=lines;
        checkoutCart.querySelectorAll('[data-remove]').forEach(btn=>btn.addEventListener('click',()=>{
          const next=getCart(); delete next[btn.dataset.remove]; saveCart(next); location.reload();
        }));
        const storeIds=new Set(products.map(p=>p.store_id));
        const subtotal=ids.reduce((sum,id)=>sum+byId[id].price*Number(cart[id]),0);
        const quantity=ids.reduce((sum,id)=>sum+Number(cart[id]),0);
        if(storeIds.size!==1){
          totals.innerHTML=`<p>상품 수량 합계 <strong>${quantity}개</strong></p><p class="notice error">서로 다른 판매처의 상품이 함께 담겨 있습니다. 한 판매처 상품만 남겨 주세요.</p>`;
          if(checkoutForm) checkoutForm.querySelector('button[type="submit"]').disabled=true;
          return;
        }
        const store=products[0];
        const fee=Number(store.delivery_fee||0); const total=subtotal+fee;
        const minOrder=Number(store.min_order||0);
        totals.innerHTML=`<p>상품 금액 <strong>${subtotal.toLocaleString('ko-KR')}원</strong></p><p>배송비 <strong>${fee.toLocaleString('ko-KR')}원</strong></p><p>상품 수량 합계 <strong>${quantity}개</strong></p><div class="final-total"><span>최종 결제금액</span><strong>${total.toLocaleString('ko-KR')}원</strong></div>${subtotal<minOrder?`<p class="notice error">최소 주문 금액은 ${minOrder.toLocaleString('ko-KR')}원입니다. 상품을 더 담아 주세요.</p>`:''}<p class="small muted">결제 전 표시 금액입니다. 실제 주문 시 서버에서 가격과 재고를 다시 확인합니다.</p>`;
      })
      .catch(()=>{
        checkoutCart.innerHTML='<p class="notice error">상품 정보를 불러오지 못했습니다. 페이지를 새로고침해 주세요.</p>';
        if(totals) totals.innerHTML='<p>최종 결제금액을 계산할 수 없습니다.</p>';
      });
  }
  if(checkoutForm) checkoutForm.addEventListener('submit',()=>{ if(cartJson) cartJson.value=JSON.stringify(getCart()); });
}
function escapeHtml(s){return String(s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));}
updateCartCount();
