package ru.cyber102.arinspector.data.remote

import okhttp3.MultipartBody
import okhttp3.ResponseBody
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Multipart
import retrofit2.http.PATCH
import retrofit2.http.POST
import retrofit2.http.Part
import retrofit2.http.Path
import retrofit2.http.Query
import ru.cyber102.arinspector.data.model.AccountDto
import ru.cyber102.arinspector.data.model.EquipmentDto
import ru.cyber102.arinspector.data.model.LoginRequest
import ru.cyber102.arinspector.data.model.LoginResponse
import ru.cyber102.arinspector.data.model.ReportDto
import ru.cyber102.arinspector.data.model.UpdateReportStatusRequest

interface PromScanApi {

    @POST("api/auth/login")
    suspend fun login(@Body request: LoginRequest): Response<LoginResponse>

    @GET("api/auth/me")
    suspend fun me(): Response<AccountDto>

    @POST("api/auth/logout")
    suspend fun logout(): Response<Unit>

    @GET("health")
    suspend fun health(): Response<ResponseBody>

    @GET("front/api/equipment")
    suspend fun getEquipmentList(): Response<List<EquipmentDto>>

    @GET("front/api/equipment/{id}")
    suspend fun getEquipment(@Path("id") id: String): Response<EquipmentDto>

    @Multipart
    @POST("front/api/inspect")
    suspend fun inspectFrame(
        @Part file: MultipartBody.Part,
        @Part equipmentId: MultipartBody.Part
    ): Response<ResponseBody>

    @Multipart
    @POST("front/api/reports")
    suspend fun createReport(
        @Part equipmentId: MultipartBody.Part,
        @Part inspectionId: MultipartBody.Part,
        @Part status: MultipartBody.Part,
        @Part comment: MultipartBody.Part,
        @Part payload: MultipartBody.Part,
        @Part assigneeId: MultipartBody.Part? = null,
        @Part photo: MultipartBody.Part? = null
    ): Response<ReportDto>

    @GET("front/api/reports")
    suspend fun getReports(
        @Query("status") status: String? = null
    ): Response<List<ReportDto>>

    @GET("front/api/reports/{id}")
    suspend fun getReport(@Path("id") id: String): Response<ReportDto>

    @PATCH("front/api/reports/{id}/status")
    suspend fun updateReportStatus(
        @Path("id") id: String,
        @Body body: UpdateReportStatusRequest
    ): Response<ReportDto>
}
