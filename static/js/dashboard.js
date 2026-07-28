/* لوحة التحكم التحليلية: فلترة حية عبر AJAX بدون إعادة تحميل الصفحة.
 * مسار عرض واحد فقط (renderDashboard) يُستخدم في أول تحميل للصفحة وفي كل تحديث فلتر لاحق،
 * حتى لا يكون فيه نسختين من نفس الـ HTML (واحدة في Django template وواحدة في JS) ممكن تختلفوا. */

(function () {
    var apiUrl = '';
    var chartInstance = null;

    function fmtAmount(n) {
        return Number(n || 0).toLocaleString('ar-EG', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }

    function fmtInt(n) {
        return Number(n || 0).toLocaleString('ar-EG');
    }

    function el(id) {
        return document.getElementById(id);
    }

    // ------------------------------------------------------------------
    // جمع الفلاتر الحالية من عناصر الفورم
    // ------------------------------------------------------------------
    function collectFilters() {
        return {
            branch: el('filterBranch').value,
            start_date: el('filterStartDate').value,
            end_date: el('filterEndDate').value,
            month: el('filterMonth').value,
            year: el('filterYear').value,
            course: el('filterCourse').value,
            employee: el('filterEmployee').value,
            payment_status: el('filterPaymentStatus').value,
        };
    }

    function buildQueryString(filters) {
        var params = new URLSearchParams();
        Object.keys(filters).forEach(function (key) {
            if (filters[key]) params.set(key, filters[key]);
        });
        return params.toString();
    }

    // ------------------------------------------------------------------
    // Fetch + render
    // ------------------------------------------------------------------
    function setLoading(isLoading) {
        var bar = el('dashFilterBar');
        if (bar) bar.classList.toggle('is-loading', isLoading);
    }

    function fetchAndRender(filters) {
        setLoading(true);
        var qs = buildQueryString(filters);
        fetch(apiUrl + (qs ? '?' + qs : ''))
            .then(function (r) {
                if (!r.ok) throw new Error('HTTP ' + r.status);
                return r.json();
            })
            .then(function (data) {
                renderDashboard(data);
            })
            .catch(function (err) {
                console.error('Dashboard fetch failed:', err);
                if (window.showError) window.showError('تعذر تحديث لوحة التحكم، حاول مرة أخرى.');
            })
            .finally(function () {
                setLoading(false);
            });
    }

    function onFilterChanged() {
        fetchAndRender(collectFilters());
    }

    // ------------------------------------------------------------------
    // Render: شريط الفلاتر (الفرع/الدورة/الموظف تُبنى من meta لأنها تعتمد على الفرع المختار)
    // ------------------------------------------------------------------
    function renderFilterMeta(meta) {
        var branchWrap = el('dashBranchWrap');
        var branchSelect = el('filterBranch');
        if (meta.can_switch_branch) {
            branchWrap.style.display = '';
            var options = '<option value="">كل الفروع</option>';
            meta.branches.forEach(function (b) {
                options += '<option value="' + b.id + '"' + (meta.selected_branch === b.id ? ' selected' : '') + '>' + b.name + '</option>';
            });
            branchSelect.innerHTML = options;
        } else {
            branchWrap.style.display = 'none';
        }

        var courseSelect = el('filterCourse');
        var courseOptions = '<option value="">كل الدورات</option>';
        meta.available_courses.forEach(function (c) {
            courseOptions += '<option value="' + c.id + '"' + (meta.selected_course === c.id ? ' selected' : '') + '>' + c.name + '</option>';
        });
        courseSelect.innerHTML = courseOptions;

        var employeeSelect = el('filterEmployee');
        var employeeOptions = '<option value="">كل الموظفين</option>';
        meta.available_employees.forEach(function (e) {
            employeeOptions += '<option value="' + e.id + '"' + (meta.selected_employee === e.id ? ' selected' : '') + '>' + e.name + '</option>';
        });
        employeeSelect.innerHTML = employeeOptions;

        el('filterStartDate').value = meta.start_date;
        el('filterEndDate').value = meta.end_date;
        el('filterMonth').value = meta.month;
        el('filterYear').value = meta.year;
        el('filterPaymentStatus').value = meta.payment_status;
    }

    // ------------------------------------------------------------------
    // Render: البطاقات
    // ------------------------------------------------------------------
    function statCard(bgClass, icon, number, label) {
        return '' +
            '<div class="col-md-2 col-6 mb-3">' +
            '  <div class="stat-card text-center ' + bgClass + '">' +
            '    <i class="fas ' + icon + ' mb-2"></i>' +
            '    <div class="number">' + number + '</div>' +
            '    <div class="label">' + label + '</div>' +
            '  </div>' +
            '</div>';
    }

    function renderCards(cards, expenseScopeNote) {
        var html = '';
        html += statCard('bg-registration', 'fa-user-plus', fmtAmount(cards.registration_amount), 'إجمالي التسجيل');
        html += statCard('bg-collection', 'fa-hand-holding-dollar', fmtAmount(cards.collection_amount), 'إجمالي التحصيل');
        html += statCard('bg-registered-students', 'fa-user-graduate', fmtInt(cards.registered_students), 'الطلاب المسجلين');
        html += statCard('bg-paid-students', 'fa-circle-check', fmtInt(cards.paid_students), 'الطلاب الدافعين');
        html += statCard('bg-expense', 'fa-wallet', fmtAmount(cards.expense_total), 'المصروفات');
        html += statCard('bg-net', 'fa-chart-line', fmtAmount(cards.net_total), 'الصافي');
        if (expenseScopeNote) {
            html += '<div class="col-12"><small class="text-muted"><i class="fas fa-circle-info me-1"></i>' +
                'المصروفات والصافي مفلترة حسب الفرع والتاريخ فقط (لا تتأثر بفلاتر الدورة/الموظف/حالة الدفع).</small></div>';
        }
        el('dash-cards').innerHTML = html;
    }

    // ------------------------------------------------------------------
    // Render: الهدف الشهري
    // ------------------------------------------------------------------
    function renderTarget(target) {
        var container = el('dash-target');
        if (!target) {
            container.innerHTML = '<div class="alert alert-light border text-muted mb-0">' +
                '<i class="fas fa-circle-info me-1"></i> الهدف الشهري يظهر فقط عند اختيار شهر كامل (مش نطاق تاريخ جزئي).</div>';
            return;
        }
        var pct = target.percentage;
        var barClass = pct >= 100 ? 'bg-success' : 'bg-warning';
        var width = Math.min(pct, 100);
        container.innerHTML = '' +
            '<div class="card">' +
            '  <div class="card-header bg-white"><h5 class="mb-0"><i class="fas fa-bullseye text-primary me-2"></i> الهدف الشهري</h5></div>' +
            '  <div class="card-body">' +
            '    <div class="row">' +
            '      <div class="col-md-4 text-center border-end"><h6 class="text-muted">الهدف</h6><h4 class="text-primary">' + fmtAmount(target.target) + '</h4></div>' +
            '      <div class="col-md-4 text-center border-end"><h6 class="text-muted">المحصّل</h6><h4 class="text-success">' + fmtAmount(target.achieved) + '</h4></div>' +
            '      <div class="col-md-4 text-center"><h6 class="text-muted">نسبة الإنجاز</h6><h4 class="' + (pct >= 100 ? 'text-success' : 'text-warning') + '">' + pct + '%</h4></div>' +
            '    </div>' +
            '    <div class="progress mt-3" style="height: 22px;"><div class="progress-bar ' + barClass + '" style="width: ' + width + '%">' + pct + '%</div></div>' +
            '  </div>' +
            '</div>';
    }

    // ------------------------------------------------------------------
    // Render: الرسم البياني
    // ------------------------------------------------------------------
    function renderChart(chart) {
        var ctx = document.getElementById('incomeExpenseChart').getContext('2d');
        if (chartInstance) chartInstance.destroy();
        chartInstance = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: chart.labels,
                datasets: [
                    { label: 'التسجيل', data: chart.registration, backgroundColor: 'rgba(102, 126, 234, 0.8)' },
                    { label: 'التحصيل', data: chart.collection, backgroundColor: 'rgba(17, 153, 142, 0.8)' },
                    { label: 'المصروفات', data: chart.expense, backgroundColor: 'rgba(245, 87, 108, 0.8)' },
                ],
            },
            options: {
                responsive: true,
                scales: { y: { beginAtZero: true, ticks: { callback: function (v) { return v.toLocaleString() + ' ر.س'; } } } },
                plugins: { legend: { position: 'bottom' } },
            },
        });
    }

    // ------------------------------------------------------------------
    // Render: آخر النشاطات
    // ------------------------------------------------------------------
    function renderActivities(activities) {
        if (!activities.length) {
            el('dash-activities').innerHTML = '<div class="text-center py-4 text-muted"><i class="fas fa-inbox fa-2x mb-2"></i><p>لا توجد نشاطات</p></div>';
            return;
        }
        var html = activities.map(function (a) {
            return '' +
                '<div class="activity-item d-flex align-items-center">' +
                '  <div class="activity-icon ' + a.type + ' me-3"><i class="fas ' + a.icon + '"></i></div>' +
                '  <div class="flex-grow-1">' +
                '    <div class="fw-bold">' + a.title + '</div>' +
                '    <small class="text-muted">' + a.description + ' &middot; ' + a.branch + '</small>' +
                '  </div>' +
                '  <small class="text-muted">' + a.time + '</small>' +
                '</div>';
        }).join('');
        el('dash-activities').innerHTML = html;
    }

    // ------------------------------------------------------------------
    // Render: التقارير
    // ------------------------------------------------------------------
    function emptyRow(colspan) {
        return '<tr><td colspan="' + colspan + '" class="text-center text-muted py-3">لا توجد بيانات</td></tr>';
    }

    function tableCard(colClass, title, icon, theadHtml, rowsHtml, colspan) {
        return '' +
            '<div class="' + colClass + ' mb-3">' +
            '  <div class="card h-100">' +
            '    <div class="card-header bg-white"><h6 class="mb-0"><i class="fas ' + icon + ' text-primary me-2"></i>' + title + '</h6></div>' +
            '    <div class="card-body p-0"><div class="table-responsive"><table class="table table-sm report-table mb-0">' +
            '      <thead class="table-light">' + theadHtml + '</thead>' +
            '      <tbody>' + (rowsHtml || emptyRow(colspan)) + '</tbody>' +
            '    </table></div></div>' +
            '  </div>' +
            '</div>';
    }

    function renderReports(reports) {
        var html = '';

        html += tableCard('col-md-4', 'أكثر الطلاب تحصيلاً', 'fa-hand-holding-dollar',
            '<tr><th>الاسم</th><th>المبلغ</th><th>عدد</th></tr>',
            reports.top_collected_students.map(function (s) {
                return '<tr><td>' + s.name + '</td><td>' + fmtAmount(s.total) + '</td><td>' + s.count + '</td></tr>';
            }).join(''), 3);

        html += tableCard('col-md-4', 'أكثر الطلاب تسجيلاً', 'fa-user-plus',
            '<tr><th>الاسم</th><th>المبلغ</th><th>عدد</th></tr>',
            reports.top_registered_students.map(function (s) {
                return '<tr><td>' + s.name + '</td><td>' + fmtAmount(s.total) + '</td><td>' + s.count + '</td></tr>';
            }).join(''), 3);

        html += tableCard('col-md-4', 'أكثر الدورات تسجيلاً', 'fa-book-open',
            '<tr><th>الدورة</th><th>عدد الطلاب</th></tr>',
            reports.most_registered_courses.map(function (c) {
                return '<tr><td>' + c.course + '</td><td>' + c.students_count + '</td></tr>';
            }).join(''), 2);

        html += tableCard('col-md-4', 'أعلى الدورات دخلاً', 'fa-sack-dollar',
            '<tr><th>الدورة</th><th>الإجمالي</th></tr>',
            reports.highest_revenue_courses.map(function (c) {
                return '<tr><td>' + c.course + '</td><td>' + fmtAmount(c.total) + '</td></tr>';
            }).join(''), 2);

        html += tableCard('col-md-4', 'أكثر الموظفين تسجيلاً', 'fa-user-tie',
            '<tr><th>الموظف</th><th>المبلغ</th><th>عدد</th></tr>',
            reports.top_employees_by_registrations.map(function (e) {
                return '<tr><td>' + e.name + '</td><td>' + fmtAmount(e.amount) + '</td><td>' + e.count + '</td></tr>';
            }).join(''), 3);

        html += tableCard('col-md-4', 'أكثر الموظفين تحصيلاً', 'fa-user-tie',
            '<tr><th>الموظف</th><th>المبلغ</th><th>عدد</th></tr>',
            reports.top_employees_by_collections.map(function (e) {
                return '<tr><td>' + e.name + '</td><td>' + fmtAmount(e.amount) + '</td><td>' + e.count + '</td></tr>';
            }).join(''), 3);

        var pvu = reports.paid_vs_unpaid;
        var pvuTotal = pvu.paid + pvu.unpaid;
        var paidPct = pvuTotal > 0 ? Math.round((pvu.paid / pvuTotal) * 100) : 0;
        html += '' +
            '<div class="col-md-4 mb-3">' +
            '  <div class="card h-100">' +
            '    <div class="card-header bg-white"><h6 class="mb-0"><i class="fas fa-scale-balanced text-primary me-2"></i>الطلاب: دافع بالكامل مقابل غير مكتمل</h6></div>' +
            '    <div class="card-body">' +
            '      <div class="d-flex justify-content-between mb-2"><span>عدد الطلاب (إجمالي)</span><strong>' + fmtInt(reports.students_count) + '</strong></div>' +
            '      <div class="d-flex justify-content-between mb-1"><span class="text-success">مكتمل الدفع (له قسط)</span><strong>' + fmtInt(pvu.paid) + '</strong></div>' +
            '      <div class="d-flex justify-content-between mb-2"><span class="text-warning">غير مكتمل (تسجيل فقط)</span><strong>' + fmtInt(pvu.unpaid) + '</strong></div>' +
            '      <div class="progress" style="height: 18px;"><div class="progress-bar bg-success" style="width: ' + paidPct + '%">' + paidPct + '%</div></div>' +
            '    </div>' +
            '  </div>' +
            '</div>';

        el('dash-reports').innerHTML = html;
    }

    function renderBranchComparison(rows) {
        var container = el('dash-branch-comparison');
        if (!rows) {
            container.innerHTML = '';
            return;
        }
        var body = rows.map(function (r) {
            var pctCell = r.achievement_percentage === null ? '-' : r.achievement_percentage + '%';
            return '' +
                '<tr><td class="fw-bold">' + r.branch + '</td>' +
                '<td>' + fmtAmount(r.registration_amount) + '</td>' +
                '<td>' + fmtAmount(r.collection_amount) + '</td>' +
                '<td>' + fmtInt(r.registered_students) + '</td>' +
                '<td>' + fmtInt(r.paid_students) + '</td>' +
                '<td>' + pctCell + '</td></tr>';
        }).join('');
        container.innerHTML = '' +
            '<div class="col-12">' +
            '  <div class="card shadow-sm">' +
            '    <div class="card-header bg-dark text-white"><h5 class="mb-0"><i class="fas fa-map-marker-alt me-2"></i> مقارنة الفروع</h5></div>' +
            '    <div class="card-body p-0"><div class="table-responsive"><table class="table table-hover mb-0">' +
            '      <thead class="table-light"><tr><th>الفرع</th><th>التسجيل</th><th>التحصيل</th><th>طلاب مسجلين</th><th>طلاب دافعين</th><th>الإنجاز</th></tr></thead>' +
            '      <tbody>' + (body || emptyRow(6)) + '</tbody>' +
            '    </table></div></div>' +
            '  </div>' +
            '</div>';
    }

    // ------------------------------------------------------------------
    // نقطة الدخول الموحدة للعرض
    // ------------------------------------------------------------------
    function renderDashboard(data) {
        renderFilterMeta(data.meta);
        renderCards(data.cards, data.expense_scope_note);
        renderTarget(data.monthly_target);
        renderChart(data.chart);
        renderActivities(data.recent_activities);
        renderReports(data.reports);
        renderBranchComparison(data.reports.branch_comparison);
    }

    // ------------------------------------------------------------------
    // Init
    // ------------------------------------------------------------------
    window.initDashboard = function (options) {
        apiUrl = options.apiUrl;

        ['filterBranch', 'filterStartDate', 'filterEndDate', 'filterMonth', 'filterYear', 'filterCourse', 'filterEmployee', 'filterPaymentStatus']
            .forEach(function (id) { el(id).addEventListener('change', onFilterChanged); });

        el('filterResetBtn').addEventListener('click', function () {
            fetchAndRender({});
        });

        var initialDataEl = document.getElementById('dashboard-initial-data');
        if (initialDataEl) {
            renderDashboard(JSON.parse(initialDataEl.textContent));
        } else {
            fetchAndRender({});
        }
    };
})();
