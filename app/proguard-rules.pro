# Keep Gson model classes
-keep class ru.cyber102.arinspector.data.** { *; }
-keepattributes Signature
-keepattributes *Annotation*

# ARCore / SceneView
-keep class com.google.ar.core.** { *; }
-dontwarn com.google.ar.core.**

# OkHttp
-dontwarn okhttp3.**
-dontwarn okio.**
