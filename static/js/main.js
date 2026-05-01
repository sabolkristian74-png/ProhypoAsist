document.addEventListener('DOMContentLoaded', function () {
  const formEls = {
    loan_amount: document.getElementById('loan_amount'),
    annual_rate: document.getElementById('annual_rate'),
    years: document.getElementById('years'),
    first_payment: document.getElementById('first_payment'),
    insurance_sum: document.getElementById('insurance_sum'),
    insurance_years: document.getElementById('insurance_years'),
    increase_pct: document.getElementById('increase_pct'),
  };

  const calculateBtn = document.getElementById('calculateBtn');
  const exportCsv = document.getElementById('exportCsv');
  const alerts = document.getElementById('alerts');
  const scheduleTableBody = document.querySelector('#scheduleTable tbody');

  let chart = null;
  function showAlert(msg, type='warning'){
    alerts.innerHTML = `<div class="alert alert-${type}">${msg}</div>`;
  }

  function clearAlert(){alerts.innerHTML=''}

  async function doCalculate(){
    clearAlert();
    const payload = {
      loan_amount: parseFloat(formEls.loan_amount.value||0),
      annual_rate: parseFloat(formEls.annual_rate.value||0),
      years: parseInt(formEls.years.value||0),
      first_payment: formEls.first_payment.value || new Date().toISOString().slice(0,10),
      insurance_sum: parseFloat(formEls.insurance_sum.value||0),
      insurance_years: parseInt(formEls.insurance_years.value||0),
      increase_pct: parseFloat(formEls.increase_pct.value||0),
    };

    // try FastAPI endpoint first, then fall back to Flask assistant endpoint
    let res = await fetch('/api/calculate',{ method:'POST', credentials: 'same-origin', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload) });
    if(res.status === 404){
      res = await fetch('/hypo/calc',{ method:'POST', credentials: 'same-origin', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload) });
    }
    if(!res.ok){ showAlert('Chyba pri výpočte','danger'); return }
    const data = await res.json();
    renderResults(data);
  }

  function renderResults(data){
    // chart data
    const labels = data.schedule.map(s => s.date);
    const balance = data.schedule.map(s => s.balance);
    const insurance = data.schedule.map(s => s.insurance);
    let optimized = null;
    if(data.optimized && data.optimized.required_initial){
      // rebuild optimized series as linear decrease from required_initial
      const init = data.optimized.required_initial;
      const months = data.schedule.length;
      optimized = Array.from({length: months}, (_,i)=>{
        const factor = Math.max(0, 1 - i/(months));
        return Math.round(init * factor * 100)/100;
      });
    }

    const ctx = document.getElementById('mainChart').getContext('2d');
    if(chart) chart.destroy();
    chart = new Chart(ctx,{
      type:'line',data:{labels, datasets:[
        {label:'Zostatok úveru', data:balance, borderColor:'red', tension:0.2, fill:false},
        {label:'Poistná suma', data:insurance, borderColor:'blue', tension:0.2, fill:false},
        ...(optimized? [{label:'Optimalizovaná PS', data:optimized, borderColor:'green', tension:0.2, fill:false}]:[])
      ]}, options:{responsive:true, interaction:{mode:'index', intersect:false}, plugins:{tooltip:{enabled:true}}}
    });

    // populate table
    scheduleTableBody.innerHTML = '';
    data.schedule.forEach(row=>{
      const tr = document.createElement('tr');
      if(row.difference < 0){ tr.classList.add('table-danger') }
      tr.innerHTML = `
        <td>${row.month}</td>
        <td>${row.date}</td>
        <td>${row.payment.toLocaleString('sk-SK',{style:'currency',currency:'EUR'})}</td>
        <td>${row.interest.toLocaleString('sk-SK',{style:'currency',currency:'EUR'})}</td>
        <td>${row.principal.toLocaleString('sk-SK',{style:'currency',currency:'EUR'})}</td>
        <td>${row.balance.toLocaleString('sk-SK',{style:'currency',currency:'EUR'})}</td>
        <td>${row.insurance.toLocaleString('sk-SK',{style:'currency',currency:'EUR'})}</td>
        <td>${row.difference.toLocaleString('sk-SK',{style:'currency',currency:'EUR'})}</td>
      `;
      scheduleTableBody.appendChild(tr);
    });

    exportCsv.onclick = ()=>{
      downloadCsv(data.schedule);
    }
  }

  function downloadCsv(rows){
    const header = ['month','date','payment','interest','principal','balance','insurance','difference'];
    const lines = [header.join(',')];
    rows.forEach(r=>{
      lines.push([r.month,r.date,r.payment,r.interest,r.principal,r.balance,r.insurance,r.difference].join(','));
    });
    const blob = new Blob([lines.join('\n')],{type:'text/csv;charset=utf-8;'});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'schedule.csv'; document.body.appendChild(a); a.click(); a.remove();
  }

  calculateBtn.addEventListener('click', doCalculate);

  // dark mode toggle
  document.getElementById('toggleDark').addEventListener('click', ()=>{
    document.body.classList.toggle('bg-dark');
    document.body.classList.toggle('text-light');
  });
});
