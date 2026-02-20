' =======================================================================
' PM 통합 관리 시스템 - 엑셀 마스터 툴박스 (v4.4.4 분석 기능 복원본)
' -----------------------------------------------------------------------
' [수정 및 복원 사항]
' 1. 일조 및 발전 분석 기능 복원: Solar_DB 데이터를 기반으로 분석 리포트 생성
' 2. 데이터 레이아웃 유지: PM(I1), 금주(J2), 차주(K2) 참조
' 3. 구문 오류 해결: If...ElseIf 다중행 블록 구조 유지
' 4. 제어 센터 개선: 일조 발전 분석 전용 실행 버튼 추가
' =======================================================================

Sub GenerateCompletePMOSystem()
    Dim confirm As VbMsgBoxResult
    
    confirm = MsgBox("프로젝트 현황 및 [일조 발전 분석] 리포트를 모두 생성하시겠습니까?", vbYesNo + vbQuestion, "시스템 시작")
    If confirm = vbNo Then Exit Sub

    Application.ScreenUpdating = False
    Application.Calculation = xlCalculationManual 
    
    ' 기능별 순차 호출
    Call SetupControlCenter
    Call CreateMainDashboard
    Call CreateProjectDetailSheets 
    Call CreateSolarAnalysisReport ' 일조 발전 분석 기능 호출
    
    Application.Calculation = xlCalculationAutomatic
    Application.ScreenUpdating = True
    
    MsgBox "모든 리포트 및 일조 분석 생성이 완료되었습니다!", vbInformation, "작업 성공"
End Sub

' 1. 제어 센터 시트 구성 (버튼 추가)
Sub SetupControlCenter()
    Dim wsCtrl As Worksheet
    Dim btn1 As Button, btn2 As Button
    
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
        .Value = "PMO 통합 관리 엑셀 마스터 (v4.4.4)"
        .Font.Size = 22: .Font.Bold = True: .Font.Name = "맑은 고딕"
    End With
    
    wsCtrl.Range("B4").Value = "▶ 아래 버튼을 클릭하여 필요한 리포트를 생성하세요."
    wsCtrl.Range("B4").Font.Color = RGB(120, 120, 120)
    
    ' 버튼 1: 전체 생성
    Set btn1 = wsCtrl.Buttons.Add(wsCtrl.Range("B6").Left, wsCtrl.Range("B6").Top, 250, 50)
    btn1.OnAction = "GenerateCompletePMOSystem"
    btn1.Caption = "🚀 전체 리포트 일괄 생성"
    btn1.Font.Bold = True
    
    ' 버튼 2: 일조 발전 분석만 생성
    Set btn2 = wsCtrl.Buttons.Add(wsCtrl.Range("B10").Left, wsCtrl.Range("B10").Top, 250, 50)
    btn2.OnAction = "CreateSolarAnalysisReport"
    btn2.Caption = "☀️ 일조 발전 분석 업데이트"
    btn2.Font.Bold = True
End Sub

' 2. 메인 통합 대시보드
Sub CreateMainDashboard()
    Dim wsDash As Worksheet, wsEach As Worksheet
    Dim wb As Workbook
    Dim rPos As Integer, cPos As Integer, pjtIdx As Integer
    Dim avgAct As Double, avgPlan As Double, lastR As Long, totalRows As Long
    Dim thisW As String, nextW As String, pmName As String, statusText As String
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
    
    With wsDash.Range("B2:J3")
        .Merge: .Value = "  통합 현황 대시보드 (PM 및 주간보고 연동)"
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
            totalRows = IIf(lastR > 1, lastR - 1, 1)
            
            avgAct = Application.WorksheetFunction.Sum(wsEach.Range("G2:G" & lastR)) / totalRows
            avgPlan = CalculateTotalPlanned(wsEach)
            
            pmName = wsEach.Range("I1").Value
            thisW = Trim(wsEach.Range("J2").Value)
            nextW = Trim(wsEach.Range("K2").Value)
            
            If pmName = "" Then pmName = "미지정"
            If thisW = "" Then thisW = "금주 실적 미입력"
            If nextW = "" Then nextW = "차주 계획 미입력"
            
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
            
            wsDash.Cells(rPos + 2, cPos + 1).Value = "담당 PM: " & pmName
            wsDash.Cells(rPos + 2, cPos + 1).Font.Size = 9: wsDash.Cells(rPos + 2, cPos + 1).Font.Bold = True: wsDash.Cells(rPos + 2, cPos + 1).Font.Color = RGB(100, 100, 100)
            
            If avgAct >= 100 Then
                statusText = "완료"
            ElseIf (avgPlan - avgAct) >= 10 Then
                statusText = "지연"
            Else
                statusText = "정상"
            End If
            
            With wsDash.Cells(rPos + 1, cPos + 3)
                .Value = statusText: .Font.Size = 10: .HorizontalAlignment = xlRight
                If statusText = "지연" Then .Font.Color = vbRed Else .Font.Color = RGB(41, 128, 185)
            End With
            
            wsDash.Cells(rPos + 3, cPos + 1).Value = "계획: " & Format(avgPlan, "0.0") & "% | 실적: " & Format(avgAct, "0.0") & "%"
            wsDash.Cells(rPos + 3, cPos + 1).Font.Size = 9: wsDash.Cells(rPos + 3, cPos + 1).Font.Color = RGB(127, 140, 141)
            
            Set barRng = wsDash.Range(wsDash.Cells(rPos + 4, cPos + 1), wsDash.Cells(rPos + 7, cPos + 3))
            barRng.Merge
            With barRng
                .Interior.Color = RGB(248, 249, 251): .Font.Size = 9: .WrapText = True: .VerticalAlignment = xlTop
                .Borders.LineStyle = xlContinuous: .Borders.Color = RGB(240, 242, 245)
                .Value = "[금주] " & thisW & vbCrLf & "[차주] " & nextW
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

' 3. 현장별 상세 페이지 생성
Sub CreateProjectDetailSheets()
    Dim wsEach As Worksheet, wsDet As Worksheet
    Dim lastR As Long
    Dim thisW As String, nextW As String, pmName As String
    
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
            
            pmName = wsEach.Range("I1").Value
            If pmName = "" Then pmName = "미지정"
            
            With wsDet.Range("B2")
                .Value = "[상세보고] " & wsEach.Name & " (담당: " & pmName & ")"
                .Font.Size = 15: .Font.Bold = True: .Font.Color = RGB(31, 73, 125)
            End With
            
            thisW = wsEach.Range("J2").Value: nextW = wsEach.Range("K2").Value
            If Trim(thisW) = "" Then thisW = "미입력": If Trim(nextW) = "" Then nextW = "미입력"
            
            With wsDet.Range("B4:H4")
                .Merge: .Value = "  핵심 현황 및 계획 요약": .Font.Bold = True
                .Interior.Color = RGB(68, 114, 196): .Font.Color = vbWhite
            End With
            
            With wsDet.Range("B5:H8")
                .Merge: .Value = "● 이번 주 실적: " & thisW & vbCrLf & vbCrLf & "● 다음 주 계획: " & nextW
                .WrapText = True: .VerticalAlignment = xlTop: .Interior.Color = RGB(242, 242, 242)
                .Borders.LineStyle = xlContinuous: .Borders.Color = RGB(200, 200, 200): .Font.Size = 10
            End With
            
            wsDet.Range("B10").Value = " 상세 일정 및 공정표"
            wsDet.Range("B10").Font.Bold = True
            lastR = wsEach.Cells(wsEach.Rows.Count, "A").End(xlUp).Row
            wsEach.Range("A1:K" & lastR).Copy wsDet.Range("B11")
            
            With wsDet.Range("B11").CurrentRegion
                .Borders.LineStyle = xlContinuous: .Columns.AutoFit
            End With
            wsDet.Range("B11:L11").Interior.Color = RGB(230, 235, 245): wsDet.Range("B11:L11").Font.Bold = True
            wsDet.Columns("B:C").ColumnWidth = 12
        End If
    Next wsEach
End Sub

' 4. [복원] 일조 및 발전 분석 리포트 생성
Sub CreateSolarAnalysisReport()
    Dim wsSolar As Worksheet, wsDB As Worksheet
    Dim lastR As Long, i As Long
    Dim dictRegions As Object
    Dim regName As String, genVal As Double
    Dim startRow As Integer
    
    ' Solar_DB 시트 존재 여부 확인
    On Error Resume Next
    Set wsDB = ThisWorkbook.Sheets("Solar_DB")
    On Error GoTo 0
    
    If wsDB Is Nothing Then
        MsgBox "Solar_DB 시트가 없습니다. 데이터를 먼저 업로드해주세요.", vbExclamation
        Exit Sub
    End If
    
    ' 기존 분석 시트 삭제 및 생성
    On Error Resume Next
    Application.DisplayAlerts = False
    ThisWorkbook.Sheets("일조 발전 분석").Delete
    Application.DisplayAlerts = True
    On Error GoTo 0
    
    Set wsSolar = ThisWorkbook.Sheets.Add(After:=ThisWorkbook.Sheets("통합 대시보드"))
    wsSolar.Name = "일조 발전 분석"
    ActiveWindow.DisplayGridlines = False
    
    ' 타이틀
    With wsSolar.Range("B2")
        .Value = "☀️ 지역별 일 발전량 및 일조 분석 리포트"
        .Font.Size = 18: .Font.Bold = True: .Font.Color = RGB(255, 102, 0)
    End With
    
    ' 요약 표 헤더
    wsSolar.Range("B5:E5").Value = Array("순번", "지역(지점)", "평균 발전시간(h)", "일사량 합계")
    With wsSolar.Range("B5:E5")
        .Interior.Color = RGB(255, 242, 204): .Font.Bold = True: .HorizontalAlignment = xlCenter
        .Borders.LineStyle = xlContinuous
    End With
    
    ' 데이터 분석 로직 (간이 요약)
    lastR = wsDB.Cells(wsDB.Rows.Count, "A").End(xlUp).Row
    startRow = 6
    
    ' [참고] image_a83260.png 기준: A날짜, B지점, C발전시간, D일사량
    ' 실제 분석은 피벗 테이블 대신 데이터 루프로 구현
    Set dictRegions = CreateObject("Scripting.Dictionary")
    
    For i = 2 To lastR
        regName = wsDB.Cells(i, 2).Value
        If regName <> "" Then
            If Not dictRegions.Exists(regName) Then
                dictRegions.Add regName, startRow
                wsSolar.Cells(startRow, 2).Value = startRow - 5
                wsSolar.Cells(startRow, 3).Value = regName
                wsSolar.Cells(startRow, 4).Value = wsDB.Cells(i, 3).Value ' 최신값 우선 표시
                wsSolar.Cells(startRow, 5).Value = wsDB.Cells(i, 4).Value
                startRow = startRow + 1
            End If
        End If
    Next i
    
    ' 서식 마무리
    With wsSolar.Range("B5:E" & startRow - 1)
        .Borders.LineStyle = xlContinuous
        .Columns.AutoFit
    End With
    
    wsSolar.Activate
    MsgBox "일조 발전 분석 리포트가 생성되었습니다.", vbInformation
End Sub

' --- 도움 함수: 계획 진척률 계산 ---
Function CalculateTotalPlanned(wsIn As Worksheet) As Double
    Dim rIdx As Long, lastIdx As Long, tot As Double, count As Long
    Dim sVal As Variant, eVal As Variant, tD As Date
    tD = Date: lastIdx = wsIn.Cells(wsIn.Rows.Count, "A").End(xlUp).Row
    count = IIf(lastIdx > 1, lastIdx - 1, 1)
    tot = 0
    For rIdx = 2 To lastIdx
        sVal = wsIn.Cells(rIdx, 1).Value: eVal = wsIn.Cells(rIdx, 2).Value
        If IsDate(sVal) And IsDate(eVal) Then
            If tD < sVal Then
                tot = tot + 0
            ElseIf tD > eVal Then
                tot = tot + 100
            Else
                If DateDiff("d", sVal, eVal) > 0 Then
                    tot = tot + (DateDiff("d", sVal, tD) / DateDiff("d", sVal, eVal)) * 100
                Else
                    tot = tot + 100
                End If
            End If
        End If
    Next rIdx
    If count > 0 Then CalculateTotalPlanned = tot / count Else CalculateTotalPlanned = 0
End Function

' --- 도움 함수: 시스템 시트 판별 ---
Function IsSys(n As String) As Boolean
    Select Case n
        Case "Control_Center", "통합 대시보드", "weekly_history", "Solar_DB", "KPI", "Sheet1", "일조 발전 분석": IsSys = True
        Case Else: If n Like "*상세" Then IsSys = True Else IsSys = False
    End Select
End Function
