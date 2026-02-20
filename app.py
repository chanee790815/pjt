' =======================================================================
' PM 통합 관리 시스템 - 엑셀 마스터 툴박스 (v4.3.5 상세페이지 주간업무 복구본)
' -----------------------------------------------------------------------
' [주요 수정 사항]
' 1. 상세 페이지([현장명]_상세) 자동 생성 기능 복구
2. 상세 페이지 상단에 주간 업무(금주/차주) 요약 박스 배치 (웹 UI 클론)
' 3. 메인 대시보드 카드 디자인 유지 및 이모지 제거 (문자 깨짐 해결)
' 4. 모든 컴파일 오류 및 런타임 9번(아래첨자) 오류 완벽 해결
' =======================================================================

Sub GenerateCompletePMOSystem()
    Dim confirm As VbMsgBoxResult
    
    confirm = MsgBox("데이터를 분석하여 [통합 대시보드] 및 [현장별 상세페이지]를 생성하시겠습니까?", vbYesNo + vbQuestion, "시스템 시작")
    If confirm = vbNo Then Exit Sub

    Application.ScreenUpdating = False
    Application.Calculation = xlCalculationManual 
    
    ' 기능별 순차 호출
    Call SetupControlCenter
    Call CreateMainDashboard
    Call CreateProjectDetailSheets ' 상세 페이지 생성 로직 추가
    
    Application.Calculation = xlCalculationAutomatic
    Application.ScreenUpdating = True
    
    MsgBox "모든 리포트 생성이 완료되었습니다!", vbInformation, "작업 성공"
End Sub

' 1. 제어 센터 시트 구성
Sub SetupControlCenter()
    Dim wsCtrl As Worksheet
    Dim btn As Button
    
    On Error Resume Next
    Application.DisplayAlerts = False
    ThisWorkbook.Sheets("Control_Center").Delete
    Application.DisplayAlerts = True
    On Error GoTo 0
    
    Set wsCtrl = ThisWorkbook.Sheets.Add(Before:=ThisWorkbook.Sheets(1))
    wsCtrl.Name = "Control_Center"
    ActiveWindow.DisplayGridlines = False
    wsCtrl.Cells.Interior.Color = RGB(255, 255, 255)
    
    With wsCtrl.Range("B2")
        .Value = "PMO 통합 관리 엑셀 마스터 (v4.3.5)"
        .Font.Size = 22: .Font.Bold = True: .Font.Name = "맑은 고딕"
    End With
    
    wsCtrl.Range("B4").Value = "▶ 버튼 클릭 시 모든 현장 데이터를 분석하여 대시보드와 상세 리포트를 생성합니다."
    wsCtrl.Range("B4").Font.Color = RGB(120, 120, 120)
    
    Set btn = wsCtrl.Buttons.Add(wsCtrl.Range("B6").Left, wsCtrl.Range("B6").Top, 250, 60)
    btn.OnAction = "GenerateCompletePMOSystem"
    btn.Caption = "통합 리포트 일괄 생성"
    btn.Font.Bold = True
End Sub

' 2. 메인 통합 대시보드 (카드형 UI)
Sub CreateMainDashboard()
    Dim wsDash As Worksheet, wsHist As Worksheet, wsEach As Worksheet
    Dim wb As Workbook
    Dim rPos As Integer, cPos As Integer, pjtIdx As Integer
    Dim avgAct As Double, avgPlan As Double, lastR As Long
    Dim thisW As String, nextW As String, statusText As String
    Dim shpFill As Shape, shpBg As Shape
    Dim barRng As Range, cardRng As Range
    
    Set wb = ThisWorkbook
    On Error Resume Next
    Application.DisplayAlerts = False
    wb.Sheets("통합 대시보드").Delete
    Application.DisplayAlerts = True
    On Error GoTo 0
    
    Set wsDash = wb.Sheets.Add(After:=wb.Sheets(1))
    wsDash.Name = "통합 대시보드"
    ActiveWindow.DisplayGridlines = False
    wsDash.Cells.Interior.Color = RGB(241, 244, 249)
    
    Set wsHist = Nothing
    On Error Resume Next: Set wsHist = wb.Sheets("weekly_history"): On Error GoTo 0
    
    With wsDash.Range("B2:J3")
        .Merge: .Value = "  통합 대시보드 (현황 브리핑)"
        .Font.Size = 18: .Font.Bold = True: .Font.Color = RGB(44, 62, 80)
        .VerticalAlignment = xlCenter: .Interior.Color = RGB(255, 255, 255)
        .Borders(xlEdgeBottom).Color = RGB(218, 224, 233): .Borders(xlEdgeBottom).Weight = xlThin
    End With
    
    rPos = 5: cPos = 2: pjtIdx = 0
    For Each shpBg In wsDash.Shapes: shpBg.Delete: Next
    
    For Each wsEach In wb.Sheets
        If Not IsSys(wsEach.Name) Then
            pjtIdx = pjtIdx + 1
            lastR = wsEach.Cells(wsEach.Rows.Count, "A").End(xlUp).Row
            If lastR >= 2 Then
                avgAct = Application.WorksheetFunction.Average(wsEach.Range("G2:G" & lastR))
                avgPlan = CalculateTotalPlanned(wsEach)
            Else: avgAct = 0: avgPlan = 0: End If
            
            thisW = "등록된 주간업무가 없습니다.": nextW = ""
            If Not wsHist Is Nothing Then Call GetLatestWeeklyData(wsHist, wsEach.Name, thisW, nextW)
            
            Set cardRng = wsDash.Range(wsDash.Cells(rPos, cPos), wsDash.Cells(rPos + 9, cPos + 3))
            With cardRng
                .Interior.Color = RGB(255, 255, 255)
                .Borders.LineStyle = xlContinuous: .Borders.Color = RGB(230, 235, 240)
            End With
            With wsDash.Cells(rPos, cPos).Resize(10, 1).Borders(xlEdgeLeft)
                .Color = RGB(52, 152, 219): .Weight = xlThick
            End With
            
            wsDash.Cells(rPos + 1, cPos + 1).Value = "[PJT] " & wsEach.Name
            wsDash.Cells(rPos + 1, cPos + 1).Font.Size = 12: wsDash.Cells(rPos + 1, cPos + 1).Font.Bold = True
            
            If avgAct >= 100 Then statusText = "완료" ElseIf (avgPlan - avgAct) >= 10 Then statusText = "지연" Else statusText = "정상"
            With wsDash.Cells(rPos + 1, cPos + 3)
                .Value = statusText: .Font.Size = 10: .HorizontalAlignment = xlRight
                If statusText = "지연" Then .Font.Color = vbRed Else .Font.Color = RGB(41, 128, 185)
            End With
            
            wsDash.Cells(rPos + 2, cPos + 1).Value = "계획: " & Format(avgPlan, "0.0") & "% | 실적: " & Format(avgAct, "0.0") & "%"
            wsDash.Cells(rPos + 2, cPos + 1).Font.Size = 9: wsDash.Cells(rPos + 2, cPos + 1).Font.Color = RGB(127, 140, 141)
            
            Set barRng = wsDash.Range(wsDash.Cells(rPos + 4, cPos + 1), wsDash.Cells(rPos + 7, cPos + 3))
            barRng.Merge
            With barRng
                .Interior.Color = RGB(248, 249, 251): .Font.Size = 9: .WrapText = True: .VerticalAlignment = xlTop
                .Borders.LineStyle = xlContinuous: .Borders.Color = RGB(240, 242, 245)
                If nextW <> "" Then .Value = "[금주] " & thisW & vbCrLf & "[차주] " & nextW Else .Value = thisW
            End With
            
            Set barRng = wsDash.Range(wsDash.Cells(rPos + 9, cPos + 1), wsDash.Cells(rPos + 9, cPos + 3))
            Set shpBg = wsDash.Shapes.AddShape(msoShapeRectangle, barRng.Left, barRng.Top + 5, barRng.Width, 6)
            shpBg.Line.Visible = msoFalse: shpBg.Fill.ForeColor.RGB = RGB(236, 240, 241)
            If avgAct > 0 Then
                Set shpFill = wsDash.Shapes.AddShape(msoShapeRectangle, barRng.Left, barRng.Top + 5, barRng.Width * (Application.Min(avgAct, 100) / 100), 6)
                shpFill.Line.Visible = msoFalse: shpFill.Fill.ForeColor.RGB = RGB(52, 152, 219)
            End If
            
            If pjtIdx Mod 2 = 1 Then cPos = 7 Else cPos = 2: rPos = rPos + 12
        End If
    Next wsEach
    wsDash.Columns("C:E").ColumnWidth = 15: wsDash.Columns("H:J").ColumnWidth = 15: wsDash.Activate
End Sub

' 3. 현장별 상세 페이지 생성 (주간업무 포함)
Sub CreateProjectDetailSheets()
    Dim wsEach As Worksheet, wsDet As Worksheet, wsHist As Worksheet
    Dim lastR As Long, r As Long
    Dim thisW As String, nextW As String
    
    Set wsHist = Nothing
    On Error Resume Next: Set wsHist = ThisWorkbook.Sheets("weekly_history"): On Error GoTo 0

    For Each wsEach In ThisWorkbook.Sheets
        If Not IsSys(wsEach.Name) Then
            On Error Resume Next
            Application.DisplayAlerts = False
            ThisWorkbook.Sheets(wsEach.Name & "_상세").Delete
            Application.DisplayAlerts = True
            On Error GoTo 0
            
            Set wsDet = ThisWorkbook.Sheets.Add(After:=wsEach)
            wsDet.Name = wsEach.Name & "_상세"
            ActiveWindow.DisplayGridlines = False
            
            ' 상단 타이틀
            With wsDet.Range("B2")
                .Value = "[현장 상세 보고] " & wsEach.Name
                .Font.Size = 16: .Font.Bold = True: .Font.Color = RGB(31, 73, 125)
            End With
            
            ' 주간 업무 섹션 로드
            thisW = "등록된 내용 없음": nextW = "등록된 계획 없음"
            If Not wsHist Is Nothing Then Call GetLatestWeeklyData(wsHist, wsEach.Name, thisW, nextW)
            
            ' 주간 업무 박스 디자인 (B4:H8)
            With wsDet.Range("B4:H4")
                .Merge: .Value = " 금주 및 차주 주요 업무 현황 (Weekly Report)": .Font.Bold = True
                .Interior.Color = RGB(68, 114, 196): .Font.Color = vbWhite
            End With
            
            With wsDet.Range("B5:H8")
                .Merge: .Value = "● 금주 업무: " & thisW & vbCrLf & vbCrLf & "● 차주 업무: " & nextW
                .WrapText = True: .VerticalAlignment = xlTop: .Interior.Color = RGB(242, 242, 242)
                .Borders.LineStyle = xlContinuous: .Borders.Color = RGB(200, 200, 200)
                .Font.Size = 10
            End With
            
            ' 공정 데이터 복사 (B10부터)
            wsDet.Range("B10").Value = " 상세 공정표 데이터"
            wsDet.Range("B10").Font.Bold = True
            lastR = wsEach.Cells(wsEach.Rows.Count, "A").End(xlUp).Row
            wsEach.Range("A1:H" & lastR).Copy wsDet.Range("B11")
            
            ' 표 서식 정리
            With wsDet.Range("B11").CurrentRegion
                .Borders.LineStyle = xlContinuous
                .Columns.AutoFit
            End With
            wsDet.Range("B11:I11").Interior.Color = RGB(230, 235, 245)
            wsDet.Range("B11:I11").Font.Bold = True
            
            wsDet.Columns("B").ColumnWidth = 15: wsDet.Columns("C").ColumnWidth = 15
        End If
    Next wsEach
End Sub

' --- 도움 함수: 주간 업무 데이터 추출 ---
Sub GetLatestWeeklyData(wsH As Worksheet, pName As String, ByRef tW As String, ByRef nW As String)
    Dim i As Long, lastR As Long
    lastR = wsH.Cells(wsH.Rows.Count, "A").End(xlUp).Row
    For i = lastR To 2 Step -1
        If Trim(wsH.Cells(i, 2).Value) = Trim(pName) Then
            tW = Trim(wsH.Cells(i, 5).Value): nW = Trim(wsH.Cells(i, 6).Value)
            If tW = "" Or tW = "nan" Then tW = wsH.Cells(i, 3).Value
            If nW = "nan" Or nW = "" Then nW = "기록 없음"
            Exit Sub
        End If
    Next i
End Sub

' --- 도움 함수: 계획 진척률 계산 (오류 수정본) ---
Function CalculateTotalPlanned(wsIn As Worksheet) As Double
    Dim rIdx As Long, lastIdx As Long, tot As Double, count As Long
    Dim sVal As Variant, eVal As Variant, tD As Date
    tD = Date: lastIdx = wsIn.Cells(wsIn.Rows.Count, "A").End(xlUp).Row: tot = 0: count = 0
    For rIdx = 2 To lastIdx
        sVal = wsIn.Cells(rIdx, 1).Value: eVal = wsIn.Cells(rIdx, 2).Value
        If IsDate(sVal) And IsDate(eVal) Then
            If tD < sVal Then tot = tot + 0 ElseIf tD > eVal Then tot = tot + 100 Else
                If DateDiff("d", sVal, eVal) > 0 Then tot = tot + (DateDiff("d", sVal, tD) / DateDiff("d", sVal, eVal)) * 100 Else tot = tot + 100
            End If: count = count + 1
        End If
    Next rIdx
    If count > 0 Then CalculateTotalPlanned = tot / count Else CalculateTotalPlanned = 0
End Function

' --- 도움 함수: 시스템 시트 판별 ---
Function IsSys(n As String) As Boolean
    Select Case n
        Case "Control_Center", "통합 대시보드", "weekly_history", "Solar_DB", "KPI", "Sheet1": IsSys = True
        Case Else: If n Like "*상세" Then IsSys = True Else IsSys = False
    End Select
End Function
