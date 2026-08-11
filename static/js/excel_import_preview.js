/* معاينة استيراد Excel: تحقق حي وتعديل داخل الجدول قبل الاعتماد النهائي.
 * stagedRows هو مصدر الحقيقة الوحيد؛ الصفحات بترندر بس صف الصفحة الحالية
 * كعناصر DOM حية (مش كل الصفوف مرة واحدة) عشان الملفات الكبيرة تفضل سريعة. */
(function () {
    function csrfToken() {
        var el = document.querySelector('[name=csrfmiddlewaretoken]');
        return el ? el.value : '';
    }

    function el(id) {
        return document.getElementById(id);
    }

    window.initExcelPreview = function (options) {
        var stagedRows = JSON.parse(document.getElementById('stagedRowsData').textContent);
        var fields = options.fields;
        var pageSize = 50;
        var currentPage = 0;

        var tbody = el('previewTableBody');
        var paginationEl = el('previewPagination');
        var summaryEl = el('previewSummaryText');
        var revalidateBtn = el('revalidateBtn');
        var commitBtn = el('commitBtn');

        function cellControl(row, field) {
            var wrap = document.createElement('div');
            var value = row.data[field.name] || '';
            var error = row.errors && row.errors[field.name];

            var input;
            if (field.type === 'select') {
                input = document.createElement('select');
                input.className = 'form-select form-select-sm';
                field.options.forEach(function (opt) {
                    var o = document.createElement('option');
                    o.value = opt[0];
                    o.textContent = opt[1];
                    if (opt[0] === value) o.selected = true;
                    input.appendChild(o);
                });
            } else {
                input = document.createElement('input');
                input.className = 'form-control form-control-sm';
                input.type = field.type === 'number' ? 'number' : (field.type === 'date' ? 'date' : 'text');
                if (field.type === 'number') input.step = '0.01';
                input.value = value;
                if (field.datalist) input.setAttribute('list', field.datalist);
            }

            if (error) input.classList.add('is-invalid');

            // تلميح "تم اختيار: ..." بيعكس نتيجة آخر تحقق من السيرفر بس، فلازم
            // نمسحه فوراً لحظة ما المستخدم يغيّر القيمة يدوياً (كتابة/قائمة/
            // إضافة دورة) وإلا هيفضل يعرض معلومة قديمة ملهاش علاقة بالقيمة الحالية
            var hintEl = null;
            function clearStaleHint() {
                if (field.matchField) row[field.matchField] = null;
                if (hintEl) {
                    hintEl.remove();
                    hintEl = null;
                }
            }

            var writeThrough = function () {
                row.data[field.name] = input.value;
                clearStaleHint();
            };
            input.addEventListener('input', writeThrough);
            input.addEventListener('change', writeThrough);

            wrap.appendChild(input);

            if (error) {
                var msg = document.createElement('div');
                msg.className = 'invalid-feedback d-block small';
                msg.textContent = error;
                wrap.appendChild(msg);
            } else if (field.matchField && row[field.matchField] && row[field.matchField].quality && row[field.matchField].quality !== 'exact') {
                var match = row[field.matchField];
                hintEl = document.createElement('div');
                hintEl.className = 'small mt-1 ' + (match.quality === 'low_confidence' ? 'text-warning' : 'text-info');
                hintEl.innerHTML = '<i class="fas fa-triangle-exclamation"></i> تم اختيار: ' + (match.resolved_name || '');
                wrap.appendChild(hintEl);
            }

            // قائمة اختيار مساعدة: بتفضل تعرض أقرب تخمين تلقائي في الخانة،
            // بس لو المستخدم حاسس إنه غلط يقدر يختار من القائمة الكاملة مباشرة
            if (field.pickList && field.pickListOptions && field.pickListOptions.length) {
                var picker = document.createElement('select');
                picker.className = 'form-select form-select-sm mt-1';
                var placeholder = document.createElement('option');
                placeholder.value = '';
                placeholder.textContent = '-- اختر من القائمة --';
                picker.appendChild(placeholder);
                field.pickListOptions.forEach(function (name) {
                    var o = document.createElement('option');
                    o.value = name;
                    o.textContent = name;
                    picker.appendChild(o);
                });
                picker.addEventListener('change', function () {
                    if (picker.value) {
                        input.value = picker.value;
                        row.data[field.name] = picker.value;
                        clearStaleHint();
                        picker.value = '';
                    }
                });
                wrap.appendChild(picker);
            }

            // زر إضافة دورة جديدة مباشرة لو الدورة المطلوبة مش موجودة أصلاً
            // في النظام، بدل ما نضطر نقبل أقرب مطابقة تقريبية غلط
            if (field.quickAddUrl) {
                var addBtn = document.createElement('button');
                addBtn.type = 'button';
                addBtn.className = 'btn btn-sm btn-outline-success mt-1 w-100';
                addBtn.innerHTML = '<i class="fas fa-plus"></i> إضافة دورة جديدة';
                addBtn.addEventListener('click', function () {
                    openQuickAddCourseModal(field.quickAddUrl, function (newName) {
                        input.value = newName;
                        row.data[field.name] = newName;
                        if (field.pickListOptions && field.pickListOptions.indexOf(newName) === -1) {
                            field.pickListOptions.push(newName);
                        }
                        clearStaleHint();
                        renderPage();
                    });
                });
                wrap.appendChild(addBtn);
            }

            return wrap;
        }

        function openQuickAddCourseModal(url, onSuccess) {
            var modalEl = el('quickAddCourseModal');
            if (!modalEl) return;
            var modal = new bootstrap.Modal(modalEl);
            var nameInput = el('quickAddCourseName');
            var priceInput = el('quickAddCoursePrice');
            var durationInput = el('quickAddCourseDuration');
            var errorEl = el('quickAddCourseError');
            var saveBtn = el('quickAddCourseSaveBtn');

            nameInput.value = '';
            priceInput.value = '';
            durationInput.value = '';
            errorEl.classList.add('d-none');

            saveBtn.onclick = function () {
                errorEl.classList.add('d-none');
                saveBtn.disabled = true;
                fetch(url, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
                    body: JSON.stringify({
                        name: nameInput.value,
                        price: priceInput.value,
                        duration_days: durationInput.value,
                    }),
                })
                    .then(function (r) { return r.json().then(function (data) { return { ok: r.ok, data: data }; }); })
                    .then(function (result) {
                        if (!result.ok) {
                            errorEl.textContent = result.data.error || 'حدث خطأ غير متوقع';
                            errorEl.classList.remove('d-none');
                            return;
                        }
                        modal.hide();
                        onSuccess(result.data.name);
                        if (window.showSuccess) window.showSuccess('تمت إضافة الدورة بنجاح.');
                    })
                    .catch(function () {
                        errorEl.textContent = 'تعذر الاتصال بالخادم.';
                        errorEl.classList.remove('d-none');
                    })
                    .finally(function () {
                        saveBtn.disabled = false;
                    });
            };

            modal.show();
        }

        function removeRow(row) {
            var idx = stagedRows.indexOf(row);
            if (idx === -1) return;
            stagedRows.splice(idx, 1);
            var maxPage = Math.max(0, Math.ceil(stagedRows.length / pageSize) - 1);
            currentPage = Math.min(currentPage, maxPage);
            renderPage();
            renderSummary();
        }

        function renderPage() {
            tbody.innerHTML = '';
            var start = currentPage * pageSize;
            var pageRows = stagedRows.slice(start, start + pageSize);

            pageRows.forEach(function (row) {
                var tr = document.createElement('tr');
                if (!row.is_valid) tr.classList.add('table-danger');

                var numTd = document.createElement('td');
                numTd.textContent = row.row_number;
                tr.appendChild(numTd);

                fields.forEach(function (field) {
                    var td = document.createElement('td');
                    td.appendChild(cellControl(row, field));
                    tr.appendChild(td);
                });

                var actionTd = document.createElement('td');
                var delBtn = document.createElement('button');
                delBtn.type = 'button';
                delBtn.className = 'btn btn-sm btn-outline-danger';
                delBtn.title = 'حذف هذا الصف نهائياً من الاستيراد';
                delBtn.innerHTML = '<i class="fas fa-trash"></i>';
                delBtn.addEventListener('click', function () {
                    if (window.confirm('حذف هذا الصف من الملف المستورد؟ لن يتم اعتماده أو رفعه نهائياً.')) {
                        removeRow(row);
                    }
                });
                actionTd.appendChild(delBtn);
                tr.appendChild(actionTd);

                tbody.appendChild(tr);
            });

            renderPagination();
        }

        function renderPagination() {
            paginationEl.innerHTML = '';
            var pageCount = Math.ceil(stagedRows.length / pageSize) || 1;
            if (pageCount <= 1) return;

            for (var p = 0; p < pageCount; p++) {
                (function (p) {
                    var btn = document.createElement('button');
                    btn.type = 'button';
                    btn.className = 'btn btn-sm ' + (p === currentPage ? 'btn-primary' : 'btn-outline-secondary');
                    btn.textContent = p + 1;
                    btn.addEventListener('click', function () {
                        currentPage = p;
                        renderPage();
                    });
                    paginationEl.appendChild(btn);
                })(p);
            }
        }

        function renderSummary() {
            if (stagedRows.length === 0) {
                summaryEl.innerHTML = '<span class="text-muted"><i class="fas fa-circle-info"></i> لا يوجد أي صفوف لاعتمادها (تم حذفها كلها)</span>';
                commitBtn.disabled = true;
                return;
            }
            var invalidCount = stagedRows.filter(function (r) { return !r.is_valid; }).length;
            if (invalidCount === 0) {
                summaryEl.innerHTML = '<span class="text-success"><i class="fas fa-circle-check"></i> جميع بيانات الملف صحيحة وجاهزة للاعتماد (' + stagedRows.length + ' صف)</span>';
                commitBtn.disabled = false;
            } else {
                summaryEl.innerHTML = '<span class="text-danger"><i class="fas fa-circle-exclamation"></i> يوجد ' + invalidCount + ' صف به أخطاء من أصل ' + stagedRows.length + ' — صحح الأخطاء ثم اضغط "إعادة التحقق"</span>';
                commitBtn.disabled = true;
            }
        }

        function fetchValidation(rows) {
            return fetch(options.revalidateUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
                body: JSON.stringify({
                    token: options.token,
                    rows: rows.map(function (r) { return { data: r.data }; }),
                }),
            }).then(function (r) { return r.json(); });
        }

        function revalidate() {
            revalidateBtn.disabled = true;
            var original = revalidateBtn.innerHTML;
            revalidateBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> جارٍ التحقق...';

            fetchValidation(stagedRows)
                .then(function (resp) {
                    if (resp.rows) {
                        stagedRows = resp.rows;
                        var maxPage = Math.max(0, Math.ceil(stagedRows.length / pageSize) - 1);
                        currentPage = Math.min(currentPage, maxPage);
                        renderPage();
                        renderSummary();
                    } else if (window.showError) {
                        window.showError('تعذر إعادة التحقق، حاول مرة أخرى.');
                    }
                })
                .catch(function () {
                    if (window.showError) window.showError('تعذر الاتصال بالخادم لإعادة التحقق.');
                })
                .finally(function () {
                    revalidateBtn.disabled = false;
                    revalidateBtn.innerHTML = original;
                });
        }

        function commit() {
            if (!stagedRows.length) return;
            commitBtn.disabled = true;
            var original = commitBtn.innerHTML;
            commitBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> جارٍ الاعتماد...';

            // نزامن السيرفر أولاً بأحدث حالة عندنا (خصوصاً لو المستخدم حذف
            // صف ولسه مضغطش "إعادة التحقق")، عشان السيرفر ميعتمدش على نسخة
            // قديمة من البيانات المرحّلة
            fetchValidation(stagedRows)
                .then(function (syncResp) {
                    if (!syncResp.rows) throw new Error('sync failed');
                    stagedRows = syncResp.rows;
                    if (!syncResp.all_valid) {
                        renderPage();
                        renderSummary();
                        if (window.showError) window.showError('تم اكتشاف تغييرات إضافية أثناء المزامنة، يرجى مراجعة الأخطاء.');
                        return null;
                    }
                    return fetch(options.commitUrl, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
                        body: JSON.stringify({ token: options.token }),
                    }).then(function (r) { return r.json(); });
                })
                .then(function (resp) {
                    if (!resp) return;
                    if (resp.success) {
                        if (window.showSuccess) window.showSuccess('تم اعتماد ورفع ' + resp.imported + ' سجل بنجاح.');
                        window.location.href = options.redirectUrl;
                        return;
                    }
                    if (resp.rows) {
                        stagedRows = resp.rows;
                        renderPage();
                        renderSummary();
                    }
                    var msg = resp.reason === 'stale_reference_data'
                        ? 'بيانات مرجعية تغيرت أثناء المراجعة (مثل دورة أو موظف)، تم إعادة التحقق تلقائياً — راجع الأخطاء الجديدة.'
                        : 'لا يزال هناك أخطاء في الملف، يرجى مراجعة البيانات وتصحيح الأخطاء الموضحة.';
                    if (window.showError) window.showError(msg);
                })
                .catch(function () {
                    if (window.showError) window.showError('تعذر الاتصال بالخادم للاعتماد.');
                })
                .finally(function () {
                    commitBtn.innerHTML = original;
                    commitBtn.disabled = stagedRows.some(function (r) { return !r.is_valid; });
                });
        }

        revalidateBtn.addEventListener('click', revalidate);
        commitBtn.addEventListener('click', commit);

        renderPage();
        renderSummary();
    };
})();
