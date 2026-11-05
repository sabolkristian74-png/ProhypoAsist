document.addEventListener('DOMContentLoaded', function () {
  const formEls = {
    loan_amount: document.getElementById('loan_amount'),
    annual_rate: document.getElementById('annual_rate'),
    years: document.getElementById('years'),
    first_payment: document.getElementById('first_payment'),
    insurance_sum: document.getElementById('insurance_sum'),
    insurance_years: document.getElementById('insurance_years'),
    increase_pct: document.getElementById('increase_pct'),
    constant_insurance: document.getElementById('constant_insurance'),
  };

  const calculateBtn = document.getElementById('calculateBtn');
  const exportCsv = document.getElementById('exportCsv');
  const alerts = document.getElementById('alerts');
  const scheduleTableBody = document.querySelector('#scheduleTable tbody');

  let chart = null;
  const currency = value => Number(value || 0).toLocaleString('sk-SK', {style:'currency', currency:'EUR'});

  function animateMetric(elementId, value, formatter = currency){
    const element = document.getElementById(elementId);
    if(!element) return;
    const previous = Number(element.dataset.value || 0);
    const started = performance.now();
    const duration = 520;
    element.dataset.value = value;
    function tick(now){
      const progress = Math.min(1, (now - started) / duration);
      const eased = 1 - Math.pow(1 - progress, 3);
      element.textContent = formatter(previous + (value - previous) * eased);
      if(progress < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  }

  function showAlert(msg, type='warning'){
    alerts.innerHTML = `<div class="alert alert-${type}">${msg}</div>`;
  }

  function clearAlert(){alerts.innerHTML=''}

  function groupScheduleByYear(schedule){
    const years = [];
    schedule.forEach(row => {
      const yearIndex = Math.floor((Number(row.month) - 1) / 12);
      let annual = years[yearIndex];
      if(!annual){
        annual = {
          year: yearIndex + 1,
          period: `${row.date} – ${row.date}`,
          payment: 0,
          interest: 0,
          principal: 0,
        };
        years[yearIndex] = annual;
      }
      annual.period = `${annual.period.split(' – ')[0]} – ${row.date}`;
      annual.payment += Number(row.payment || 0);
      annual.interest += Number(row.interest || 0);
      annual.principal += Number(row.principal || 0);
      annual.balance = Number(row.balance || 0);
      annual.insurance = Number(row.insurance_total ?? (Number(row.insurance || 0) + Number(row.constant_insurance || 0)));
      annual.difference = Number(row.difference || 0);
    });
    return years;
  }

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
      constant_insurance: parseFloat(formEls.constant_insurance.value||0),
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
    const firstRow = data.schedule[0] || {};
    const lastRow = data.schedule[data.schedule.length - 1] || {};
    const loanAmount = Number(formEls.loan_amount.value || 0);
    const initialInsurance = Number(formEls.insurance_sum.value || 0) * (1 + Number(formEls.increase_pct.value || 0) / 100);
    const constantInsurance = Number(formEls.constant_insurance.value || 0);
    const coverage = loanAmount ? ((initialInsurance + constantInsurance) / loanAmount) * 100 : 0;
    animateMetric('monthlyPayment', Number(data.monthly_payment));
    animateMetric('totalInterest', Number(data.total_interest));
    animateMetric('coverageValue', coverage, value => `${value.toFixed(0)} %`);
    document.getElementById('coverageNote').textContent = `${currency(initialInsurance + constantInsurance)} počiatočné krytie`;
    document.getElementById('chartPeriod').textContent = `${Math.round(data.schedule.length / 12)} rokov`;

    // chart data
    const labels = data.schedule.map(s => s.date);
    const balance = data.schedule.map(s => s.balance);
    const insurance = data.schedule.map(s => s.insurance_total ?? (Number(s.insurance || 0) + Number(s.constant_insurance || 0)));
    const annualRows = groupScheduleByYear(data.schedule);
    const underinsuredRows = annualRows.filter(row => row.difference < 0);
    if (underinsuredRows.length) {
      const firstUnderinsured = underinsuredRows[0];
      const worstUnderinsurance = Math.max(...underinsuredRows.map(row => Math.abs(row.difference)));
      let recommendation = '';
      if (data.optimized && data.optimized.required_initial != null) {
        const recommendedTotal = Number(data.optimized.required_initial) + constantInsurance;
        const currentTotal = initialInsurance + constantInsurance;
        const increase = Math.max(0, recommendedTotal - currentTotal);
        recommendation = ` Odporúčaná počiatočná celková PS je ${currency(recommendedTotal)}`
          + (increase > 0 ? ` (navýšenie o ${currency(increase)}).` : '.');
      }
      showAlert(
        `Podpoistenie vznikne v ${firstUnderinsured.year}. roku (${firstUnderinsured.period}). `
        + `Najvyššie podpoistenie je ${currency(worstUnderinsurance)}.${recommendation}`,
        'danger',
      );
    } else {
      showAlert('Poistná suma pokrýva zostatok úveru počas celej doby splácania.', 'success');
    }
    let optimized = null;
    if(data.optimized && data.optimized.required_initial){
      // rebuild optimized series as linear decrease from required_initial
      const init = data.optimized.required_initial;
      const months = data.schedule.length;
      const insuranceYears = Number(formEls.insurance_years.value || 0);
      optimized = Array.from({length: months}, (_,i)=>{
        const elapsedYears = insuranceYears ? Math.min(insuranceYears, Math.floor(i / 12)) : 0;
        const factor = insuranceYears ? Math.max(0, 1 - elapsedYears / insuranceYears) : 0;
        return Math.round((init * factor + constantInsurance) * 100)/100;
      });
    }

    const ctx = document.getElementById('mainChart').getContext('2d');
    if(chart) chart.destroy();
    chart = new Chart(ctx,{
      type:'line',data:{labels, datasets:[
        {label:'Zostatok úveru', data:balance, borderColor:'#0D2E6A', backgroundColor:'rgba(13,46,106,.10)', tension:0.3, fill:true, pointRadius:0, borderWidth:3},
        {label:'Poistná suma', data:insurance, borderColor:'#FF804F', tension:0.3, fill:false, pointRadius:0, borderWidth:2},
        ...(optimized? [{label:'Optimalizovaná PS', data:optimized, borderColor:'#8aa8c8', tension:0.3, fill:false, pointRadius:0, borderWidth:2}]:[])
      ]}, options:{responsive:true, maintainAspectRatio:false, interaction:{mode:'index', intersect:false}, scales:{x:{grid:{display:false}, ticks:{maxTicksLimit:6, color:'#77727f'}}, y:{grid:{color:'rgba(119,114,127,.12)'}, ticks:{color:'#77727f', callback:value => `${Math.round(value / 1000)}k`}}}, plugins:{legend:{labels:{usePointStyle:true, boxWidth:8, color:'#77727f', font:{size:11}}}, tooltip:{enabled:true, callbacks:{label:context => `${context.dataset.label}: ${currency(context.raw)}`}}}, animation:{duration:700, easing:'easeOutQuart'}}
    });

    // populate table
    scheduleTableBody.innerHTML = '';
    annualRows.forEach(row=>{
      const tr = document.createElement('tr');
      if(row.difference < 0){ tr.classList.add('table-danger') }
      tr.innerHTML = `
        <td>${row.year}. rok</td>
        <td>${row.period}</td>
        <td>${currency(row.payment)}</td>
        <td>${currency(row.interest)}</td>
        <td>${currency(row.principal)}</td>
        <td>${currency(row.balance)}</td>
        <td>${currency(row.insurance_total ?? (Number(row.insurance || 0) + Number(row.constant_insurance || 0)))}</td>
        <td>${currency(row.difference)}</td>
      `;
      scheduleTableBody.appendChild(tr);
    });

    exportCsv.onclick = ()=>{
      downloadCsv(annualRows);
    }
  }

  function downloadCsv(rows){
    const header = ['year','period','payment','interest','principal','balance','insurance','difference'];
    const lines = [header.join(',')];
    rows.forEach(r=>{
      lines.push([r.year,r.period,r.payment,r.interest,r.principal,r.balance,r.insurance,r.difference].join(','));
    });
    const blob = new Blob([lines.join('\n')],{type:'text/csv;charset=utf-8;'});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'schedule.csv'; document.body.appendChild(a); a.click(); a.remove();
  }

  calculateBtn.addEventListener('click', doCalculate);
  doCalculate();

  // dark mode toggle
  document.getElementById('toggleDark').addEventListener('click', ()=>{
    document.body.classList.toggle('bg-dark');
    document.body.classList.toggle('text-light');
  });
});
