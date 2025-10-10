from django.contrib import admin
from .models import (
    College, Category, Section, SubjectiveOptionTemplate, SubjectiveOption,
    Question, Option, Student, StudentResponse, StudentSectionResult,
    CollegeAdminProfile
)
from .forms import (
    StudentResponseAdminForm, StudentSectionResultAdminForm, OptionInlineFormSet,
    SectionAdminForm 
)

admin.site.register(CollegeAdminProfile)


def is_college_admin(user):
    if user.is_superuser:
        return False
    return user.groups.filter(name='College Administrator').exists()


class CollegeFilter(admin.SimpleListFilter):
    title = 'College'
    parameter_name = 'college'

    def lookups(self, request, model_admin):
        if is_college_admin(request.user):
            try:
                college = request.user.collegeadminprofile.college
                return ((college.id, str(college)),)
            except CollegeAdminProfile.DoesNotExist:
                return []
        if request.user.is_superuser:
            return [(c.id, str(c)) for c in College.objects.all()]
        return []

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(college__id=self.value())
        return queryset

class CategoryFilter(admin.SimpleListFilter):
    title = 'Category'
    parameter_name = 'category'

    def lookups(self, request, model_admin):
        if is_college_admin(request.user):
            try:
                college = request.user.collegeadminprofile.college
                return [(cat.id, str(cat)) for cat in Category.objects.filter(college=college)]
            except CollegeAdminProfile.DoesNotExist:
                return []
        if request.user.is_superuser:
            return [(cat.id, str(cat)) for cat in Category.objects.all()]
        return []

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(category__id=self.value())
        return queryset

class SectionFilter(admin.SimpleListFilter):
    title = 'Section'
    parameter_name = 'section'

    def lookups(self, request, model_admin):
        if is_college_admin(request.user):
            try:
                college = request.user.collegeadminprofile.college
                return [(sec.id, str(sec)) for sec in Section.objects.filter(category__college=college)]
            except CollegeAdminProfile.DoesNotExist:
                return []
        if request.user.is_superuser:
            return [(sec.id, str(sec)) for sec in Section.objects.all()]
        return []

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(section__id=self.value())
        return queryset


class CategoryInline(admin.TabularInline): model = Category; extra = 1; show_change_link = True
class OptionInline(admin.TabularInline): model = Option; formset = OptionInlineFormSet; extra = 2; fields = ('text', 'is_correct'); show_change_link = True
class QuestionInline(admin.TabularInline): model = Question; extra = 1; show_change_link = True
class SectionInline(admin.TabularInline): model = Section; extra = 1; show_change_link = True
class SubjectiveOptionInline(admin.TabularInline): model = SubjectiveOption; extra = 2


@admin.register(College)
class CollegeAdmin(admin.ModelAdmin):
    list_display = ('name', 'id'); search_fields = ('name',); inlines = [CategoryInline]; ordering = ['name']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser: return qs
        if is_college_admin(request.user):
            try: return qs.filter(id=request.user.collegeadminprofile.college.id)
            except CollegeAdminProfile.DoesNotExist: return qs.none()
        return qs.none()

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'college', 'has_correct_answers'); search_fields = ('name', 'college__name'); inlines = [SectionInline]; ordering = ['college', 'name']
    
    def get_list_filter(self, request):
        if is_college_admin(request.user):
            return ('has_correct_answers',)
        return (CollegeFilter, 'has_correct_answers')
    
    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related('college')
        if request.user.is_superuser: return qs
        if is_college_admin(request.user):
            try: return qs.filter(college=request.user.collegeadminprofile.college)
            except CollegeAdminProfile.DoesNotExist: return qs.none()
        return qs.none()
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "college" and is_college_admin(request.user):
            kwargs["queryset"] = College.objects.filter(id=request.user.collegeadminprofile.college.id)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    form = SectionAdminForm 
    list_display = ('name', 'category', 'college', 'subjective_option_template'); search_fields = ('name', 'category__name', 'category__college__name'); inlines = [QuestionInline]; ordering = ['category__college__name', 'category__name', 'name']
    
    def college(self, obj): return obj.category.college.name
    
    def get_list_filter(self, request):
        if is_college_admin(request.user):
            return (CategoryFilter,)
        return ('category__college', 'category')

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related('category', 'category__college')
        if request.user.is_superuser: return qs
        if is_college_admin(request.user):
            try: return qs.filter(category__college=request.user.collegeadminprofile.college)
            except CollegeAdminProfile.DoesNotExist: return qs.none()
        return qs.none()
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "category" and is_college_admin(request.user):
            kwargs["queryset"] = Category.objects.filter(college=request.user.collegeadminprofile.college)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

@admin.register(SubjectiveOptionTemplate)
class SubjectiveOptionTemplateAdmin(admin.ModelAdmin):
    list_display = ('name',); search_fields = ('name',); inlines = [SubjectiveOptionInline]

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('short_text', 'section', 'category', 'college'); search_fields = ('text', 'section__name', 'section__category__name'); inlines = [OptionInline]; ordering = ['section__category__college__name', 'section__name']
    
    def short_text(self, obj): return obj.text[:60]
    def category(self, obj): return obj.section.category.name
    def college(self, obj): return obj.section.category.college.name
    
    def get_list_filter(self, request):
        if is_college_admin(request.user):
            return (SectionFilter,)
        return ('section__category__college', 'section__category')

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related('section', 'section__category', 'section__category__college')
        if request.user.is_superuser: return qs
        if is_college_admin(request.user):
            try: return qs.filter(section__category__college=request.user.collegeadminprofile.college)
            except CollegeAdminProfile.DoesNotExist: return qs.none()
        return qs.none()
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "section" and is_college_admin(request.user):
            kwargs["queryset"] = Section.objects.filter(category__college=request.user.collegeadminprofile.college).select_related('category', 'category__college')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('student_id', 'name', 'college', 'created_at'); list_filter = ('college',); search_fields = ('student_id', 'name', 'college__name'); ordering = ['college__name', 'student_id']

    def get_list_filter(self, request):
        if is_college_admin(request.user):
            return ()
        return (CollegeFilter,)
    
    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related('college')
        if request.user.is_superuser: return qs
        if is_college_admin(request.user):
            try: return qs.filter(college=request.user.collegeadminprofile.college)
            except CollegeAdminProfile.DoesNotExist: return qs.none()
        return qs.none()
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "college" and is_college_admin(request.user):
            kwargs["queryset"] = College.objects.filter(id=request.user.collegeadminprofile.college.id)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

@admin.register(StudentResponse)
class StudentResponseAdmin(admin.ModelAdmin):
    form = StudentResponseAdminForm
    list_display = ('student', 'question', 'selected_option', 'submitted_at'); list_filter = ('student__college', 'question__section__category'); search_fields = ('student__name', 'question__text'); date_hierarchy = 'submitted_at'; ordering = ['-submitted_at']
    
    def get_list_filter(self, request):
        if is_college_admin(request.user):
            return (SectionFilter, )
        return ('student__college', 'question__section__category')

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related('student', 'student__college', 'question', 'selected_option')
        if request.user.is_superuser: return qs
        if is_college_admin(request.user):
            try: return qs.filter(student__college=request.user.collegeadminprofile.college)
            except CollegeAdminProfile.DoesNotExist: return qs.none()
        return qs.none()

@admin.register(StudentSectionResult)
class StudentSectionResultAdmin(admin.ModelAdmin):
    form = StudentSectionResultAdminForm
    list_display = ('student', 'section', 'total_marks'); list_filter = ('section__category__college',); search_fields = ('student__name', 'section__name'); ordering = ['student__college__name', 'student__student_id']

    def get_list_filter(self, request):
        if is_college_admin(request.user):
            return (SectionFilter,)
        return ('section__category__college',)

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related('student', 'student__college', 'section', 'section__category')
        if request.user.is_superuser: return qs
        if is_college_admin(request.user):
            try: return qs.filter(student__college=request.user.collegeadminprofile.college)
            except CollegeAdminProfile.DoesNotExist: return qs.none()
        return qs.none()